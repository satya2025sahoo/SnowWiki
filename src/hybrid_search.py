"""
src/hybrid_search.py
====================
Hybrid Search Engine (Dense Vector Cosine + BM25 Sparse Keyword Retrieval)
with Reciprocal Rank Fusion (RRF) for SnowWiki.

Combines semantic meaning (ChromaDB dense embeddings) with precise technical
term matching (Okapi BM25) tailored for ServiceNow documentation (table names,
sys_ids, script includes, error codes, and camelCase tokens).
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

from src.ingestion.core import get_chroma_collection, get_embedder

logger = logging.getLogger(__name__)

# Standard English stop words (minimal list to avoid removing technical ServiceNow terms)
_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "did", "do", "does", "doing", "don",
    "down", "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "s",
    "same", "she", "should", "so", "some", "such", "t", "than", "that", "the",
    "their", "theirs", "them", "themselves", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "will", "with", "you", "your", "yours", "yourself", "yourselves",
}

_INDEX_CACHE: Dict[str, "BranchBM25Index"] = {}
_CACHE_LOCK = threading.Lock()


def bm25_tokenize(text: str) -> List[str]:
    """ServiceNow-aware tokenizer.

    Extracts:
    1. Lowercase alphanumeric tokens including underscores and hyphens (e.g. 'sn_customerservice_case')
    2. Sub-tokens split on underscores, hyphens, and camelCase boundaries
    Filters out common stop words while preserving technical symbols.
    """
    if not text:
        return []

    # Find raw tokens (including underscores, hyphens, and dots)
    raw_tokens = re.findall(r"[a-zA-Z0-9_\-\.]+", text.lower())
    tokens: List[str] = []

    for tok in raw_tokens:
        tok_clean = tok.strip(".-_")
        if not tok_clean:
            continue

        if tok_clean not in _STOP_WORDS:
            tokens.append(tok_clean)

        # Sub-split compound tokens (e.g. sn_customerservice_case -> sn, customerservice, case)
        if "_" in tok_clean or "-" in tok_clean or "." in tok_clean:
            sub_parts = re.split(r"[_\-\.]+", tok_clean)
            for part in sub_parts:
                if len(part) > 1 and part not in _STOP_WORDS:
                    tokens.append(part)

    return tokens


class BranchBM25Index:
    """In-memory BM25 index for a specific branch's child chunks."""

    def __init__(
        self,
        branch_name: str,
        doc_ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        bm25: BM25Okapi,
        chunk_count: int,
    ):
        self.branch_name = branch_name
        self.doc_ids = doc_ids
        self.documents = documents
        self.metadatas = metadatas
        self.bm25 = bm25
        self.chunk_count = chunk_count

    @classmethod
    def build(cls, branch_name: str) -> Optional["BranchBM25Index"]:
        """Build a BM25 index by reading all child chunks for this branch from ChromaDB."""
        collection = get_chroma_collection()
        try:
            data = collection.get(
                where={"branch": branch_name},
                include=["documents", "metadatas"],
            )
        except Exception as exc:
            logger.error(f"Failed to fetch chunks from ChromaDB for branch '{branch_name}': {exc}")
            return None

        ids = data.get("ids") or []
        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []

        if not ids or not documents:
            logger.info(f"No chunks found in branch '{branch_name}' for BM25 indexing.")
            return None

        tokenized_corpus = [bm25_tokenize(doc) for doc in documents]
        bm25 = BM25Okapi(tokenized_corpus)

        logger.info(f"Built BM25 index for branch '{branch_name}' with {len(ids)} chunk(s).")
        return cls(
            branch_name=branch_name,
            doc_ids=ids,
            documents=documents,
            metadatas=metadatas,
            bm25=bm25,
            chunk_count=len(ids),
        )

    def search(self, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        """Query BM25 index and return ranked list of matches."""
        tokens = bm25_tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)
        scored_pairs = [
            (idx, float(score))
            for idx, score in enumerate(scores)
            if score > 0.0
        ]
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        results = []
        for rank, (idx, score) in enumerate(scored_pairs[:top_k], start=1):
            results.append({
                "id": self.doc_ids[idx],
                "document": self.documents[idx],
                "metadata": self.metadatas[idx],
                "bm25_score": score,
                "sparse_rank": rank,
            })
        return results


def get_or_build_branch_bm25_index(branch_name: str) -> Optional[BranchBM25Index]:
    """Get cached BM25 index for branch, rebuilding only if not cached or invalidated."""
    with _CACHE_LOCK:
        cached = _INDEX_CACHE.get(branch_name)
        if cached is not None:
            return cached

    # Build index if not yet cached
    new_index = BranchBM25Index.build(branch_name)
    if new_index:
        with _CACHE_LOCK:
            _INDEX_CACHE[branch_name] = new_index
    return new_index


def invalidate_branch_index(branch_name: str) -> None:
    """Clear cached BM25 index when new files are ingested."""
    with _CACHE_LOCK:
        if branch_name in _INDEX_CACHE:
            del _INDEX_CACHE[branch_name]
            logger.info(f"Invalidated cached BM25 index for branch '{branch_name}'")


def hybrid_search(
    query: str,
    active_branch: str,
    top_k: int = 5,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
    rrf_k: int = 60,
) -> Dict[str, Any]:
    """Execute Hybrid Retrieval combining Dense Vector Search + BM25 Sparse Search.

    Fuses candidates using Reciprocal Rank Fusion (RRF):
        RRF_score(d) = dense_weight / (rrf_k + dense_rank) + sparse_weight / (rrf_k + sparse_rank)

    Returns a ChromaDB-compatible dictionary:
        {
            "ids": [[...]],
            "documents": [[...]],
            "metadatas": [[...]],
            "distances": [[...]],
            "raw_dense_hits": [...],
            "raw_bm25_hits": [...],
            "fused_results": [...],
        }
    """
    embedder = get_embedder()
    collection = get_chroma_collection()

    candidate_pool_size = max(top_k * 3, 15)

    # ── 1. Dense Vector Retrieval ─────────────────────────────────────────────
    dense_hits: List[Dict[str, Any]] = []
    dense_ranks: Dict[str, int] = {}
    dense_sims: Dict[str, float] = {}

    try:
        query_vector = embedder.encode([query]).tolist()
        dense_res = collection.query(
            query_embeddings=query_vector,
            n_results=candidate_pool_size,
            where={"branch": active_branch},
        )
        if dense_res and dense_res.get("ids") and dense_res["ids"][0]:
            for rank, (cid, doc, meta, dist) in enumerate(
                zip(
                    dense_res["ids"][0],
                    dense_res["documents"][0],
                    dense_res["metadatas"][0],
                    dense_res["distances"][0],
                ),
                start=1,
            ):
                sim = max(0.0, 1.0 - dist)
                dense_hits.append({
                    "id": cid,
                    "document": doc,
                    "metadata": meta,
                    "similarity": sim,
                    "dense_rank": rank,
                })
                dense_ranks[cid] = rank
                dense_sims[cid] = sim
    except Exception as exc:
        logger.warning(f"Dense vector search failed: {exc}")

    # ── 2. Sparse BM25 Keyword Retrieval ──────────────────────────────────────
    bm25_hits: List[Dict[str, Any]] = []
    bm25_ranks: Dict[str, int] = {}
    bm25_scores: Dict[str, float] = {}

    try:
        bm25_idx = get_or_build_branch_bm25_index(active_branch)
        if bm25_idx:
            bm25_hits = bm25_idx.search(query, top_k=candidate_pool_size)
            for hit in bm25_hits:
                cid = hit["id"]
                bm25_ranks[cid] = hit["sparse_rank"]
                bm25_scores[cid] = hit["bm25_score"]
    except Exception as exc:
        logger.warning(f"BM25 search failed: {exc}")

    # ── 3. Reciprocal Rank Fusion (RRF) ────────────────────────────────────────
    # Gather all candidate IDs
    all_candidate_ids = list(dict.fromkeys(list(dense_ranks.keys()) + list(bm25_ranks.keys())))

    # Lookup dicts for documents and metadata
    doc_map: Dict[str, str] = {}
    meta_map: Dict[str, Dict[str, Any]] = {}

    for h in dense_hits:
        doc_map[h["id"]] = h["document"]
        meta_map[h["id"]] = h["metadata"]
    for h in bm25_hits:
        doc_map[h["id"]] = h["document"]
        meta_map[h["id"]] = h["metadata"]

    fused_candidates: List[Dict[str, Any]] = []

    # Max BM25 score for normalization
    max_bm25 = max(bm25_scores.values()) if bm25_scores else 1.0

    for cid in all_candidate_ids:
        d_rank = dense_ranks.get(cid)
        s_rank = bm25_ranks.get(cid)

        # Standard RRF formula
        rrf_score = 0.0
        if d_rank is not None:
            rrf_score += dense_weight / (rrf_k + d_rank)
        if s_rank is not None:
            rrf_score += sparse_weight / (rrf_k + s_rank)

        d_sim = dense_sims.get(cid, 0.0)
        s_score = bm25_scores.get(cid, 0.0)

        # Compute calibrated similarity score for downstream threshold gating
        # If BM25 matched strongly (keyword match) and dense has at least partial signal,
        # boost calibrated score so exact technical terms pass SIMILARITY_THRESHOLD.
        calibrated_sim = d_sim
        if s_score > 0 and max_bm25 > 0:
            norm_bm25 = min(1.0, s_score / max_bm25)
            # Boost if BM25 confirms technical relevance
            if d_sim >= 0.30:
                calibrated_sim = max(d_sim, 0.46 + 0.15 * norm_bm25)
            elif norm_bm25 >= 0.70:
                calibrated_sim = max(d_sim, 0.48)

        fused_candidates.append({
            "id": cid,
            "document": doc_map.get(cid, ""),
            "metadata": meta_map.get(cid, {}),
            "rrf_score": rrf_score,
            "dense_rank": d_rank,
            "sparse_rank": s_rank,
            "dense_similarity": d_sim,
            "bm25_score": s_score,
            "calibrated_similarity": calibrated_sim,
        })

    # Sort by RRF score descending
    fused_candidates.sort(key=lambda x: x["rrf_score"], reverse=True)
    top_fused = fused_candidates[:top_k]

    # Format return dict to match ChromaDB schema
    out_ids: List[str] = [c["id"] for c in top_fused]
    out_docs: List[str] = [c["document"] for c in top_fused]
    out_metas: List[Dict[str, Any]] = [c["metadata"] for c in top_fused]
    out_dists: List[float] = [max(0.0, 1.0 - c["calibrated_similarity"]) for c in top_fused]

    return {
        "ids": [out_ids],
        "documents": [out_docs],
        "metadatas": [out_metas],
        "distances": [out_dists],
        "raw_dense_hits": dense_hits,
        "raw_bm25_hits": bm25_hits,
        "fused_results": top_fused,
    }
