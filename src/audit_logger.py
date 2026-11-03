"""
src/audit_logger.py
===================
Enterprise Candidate Trace & Retrieval Audit Logger for SnowWiki.

Captures the full multi-stage retrieval funnel for every query:
  Stage 1: Dense Semantic Hits (Qdrant Cosine Similarity)
  Stage 2: Sparse Keyword Hits (Okapi BM25 ServiceNow tokens)
  Stage 3: Reciprocal Rank Fusion (RRF merged candidates)
  Stage 4: Cross-Encoder Reranker (BGE-Reranker scores & gating)
  Stage 5: Top-N Context Candidates fed to LLM

Persists traces to `data/eval/audit_traces.jsonl` for offline analysis,
retrieval tuning, and regression benchmarking.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from src.config import DATA_DIR, RERANK_SCORE_THRESHOLD

logger = logging.getLogger(__name__)

AUDIT_DIR = os.path.join(DATA_DIR, "eval")
AUDIT_LOG_FILE = os.path.join(AUDIT_DIR, "audit_traces.jsonl")


def _ensure_dir() -> None:
    os.makedirs(AUDIT_DIR, exist_ok=True)


def build_candidate_trace(
    query_id: str,
    query_text: str,
    branch: str,
    hybrid_res: Dict[str, Any],
    top_reranked: List[Dict[str, Any]],
    top_rerank_score: Optional[float],
    latency_ms: float = 0.0,
) -> Dict[str, Any]:
    """
    Construct a structured candidate progression trace tracking documents
    across Dense, Sparse, RRF, and Cross-Encoder stages.
    """
    raw_dense = hybrid_res.get("raw_dense_hits", [])
    raw_bm25 = hybrid_res.get("raw_bm25_hits", [])
    fused = hybrid_res.get("fused_results", [])

    # Index by candidate ID
    dense_map = {h["id"]: h for h in raw_dense}
    bm25_map = {h["id"]: h for h in raw_bm25}
    rerank_map = {h["id"]: h for h in top_reranked}

    all_ids = list(dict.fromkeys(
        [h["id"] for h in top_reranked] +
        [h["id"] for h in fused[:15]] +
        [h["id"] for h in raw_dense[:10]] +
        [h["id"] for h in raw_bm25[:10]]
    ))

    progression: List[Dict[str, Any]] = []
    for cid in all_ids:
        d_hit = dense_map.get(cid)
        b_hit = bm25_map.get(cid)
        r_hit = rerank_map.get(cid)

        # Snippet preview
        doc_preview = ""
        meta = {}
        if r_hit:
            doc_preview = r_hit.get("document", "")[:120].strip().replace("\n", " ")
            meta = r_hit.get("metadata", {})
        elif d_hit:
            doc_preview = d_hit.get("document", "")[:120].strip().replace("\n", " ")
            meta = d_hit.get("metadata", {})
        elif b_hit:
            doc_preview = b_hit.get("document", "")[:120].strip().replace("\n", " ")
            meta = b_hit.get("metadata", {})

        dense_rank = d_hit.get("dense_rank") if d_hit else None
        dense_sim = round(d_hit.get("similarity", 0.0), 3) if d_hit else None

        sparse_rank = b_hit.get("sparse_rank") if b_hit else None
        bm25_score = round(b_hit.get("bm25_score", 0.0), 2) if b_hit else None

        # Find RRF rank in fused list
        fused_rank = None
        rrf_score = None
        for fr_idx, fr in enumerate(fused, 1):
            if fr["id"] == cid:
                fused_rank = fr_idx
                rrf_score = round(fr.get("rrf_score", 0.0), 4)
                break

        rerank_score = round(r_hit.get("rerank_score", 0.0), 4) if r_hit else None
        rerank_rank = r_hit.get("rank") if r_hit else None

        # Status
        status = "Pruned"
        if r_hit:
            if rerank_score is not None and rerank_score >= RERANK_SCORE_THRESHOLD:
                status = f"Selected (Rank {rerank_rank})"
            else:
                status = "Gated (Below Threshold)"

        source_file = meta.get("source_file") or meta.get("source") or "Unknown"

        progression.append({
            "chunk_id": cid,
            "source_file": source_file,
            "snippet": doc_preview,
            "dense_rank": dense_rank,
            "dense_similarity": dense_sim,
            "sparse_rank": sparse_rank,
            "bm25_score": bm25_score,
            "rrf_rank": fused_rank,
            "rrf_score": rrf_score,
            "rerank_score": rerank_score,
            "status": status,
        })

    trace = {
        "query_id": query_id,
        "query": query_text,
        "branch": branch,
        "timestamp": datetime.datetime.now().isoformat(),
        "latency_ms": round(latency_ms, 1),
        "total_dense_hits": len(raw_dense),
        "total_sparse_hits": len(raw_bm25),
        "total_fused_candidates": len(fused),
        "top_rerank_score": round(top_rerank_score, 4) if top_rerank_score is not None else None,
        "threshold": RERANK_SCORE_THRESHOLD,
        "gated_out": top_rerank_score is not None and top_rerank_score < RERANK_SCORE_THRESHOLD,
        "selected_chunks_count": len(top_reranked),
        "candidates_progression": progression,
    }
    return trace


def log_audit_trace(trace: Dict[str, Any]) -> None:
    """Append a structured candidate progression trace to data/eval/audit_traces.jsonl."""
    _ensure_dir()
    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning(f"Failed to append to {AUDIT_LOG_FILE}: {exc}")
