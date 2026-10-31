"""
tests/eval_rag.py
=================
Automated Evaluation Harness for SnowWiki Retrieval Pipeline.
Evaluates the full retrieval stack:
  Dense Cosine Embeddings + Okapi BM25 (Hybrid RRF) + Cross-Encoder Reranker (BAAI/bge-reranker-base)

Benchmark Metrics:
- Recall@1 (Top Rank Precision)
- Recall@5 (Top-5 Coverage)
- Mean Reciprocal Rank (MRR@5)
- Anti-Hallucination Rejection Accuracy (Out-of-Scope Gating)
- Average Retrieval Latency (ms)
"""

from __future__ import annotations

import json
import os
import sys
import time

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.config import RERANK_CANDIDATE_POOL_SIZE, RERANK_SCORE_THRESHOLD, RERANK_TOP_N
from src.hybrid_search import hybrid_search
from src.reranker import rerank_candidates

GOLDEN_QA_PATH = os.path.join(BASE_DIR, "data", "eval", "golden_qa.json")


def _safe_print(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def evaluate_reranked_retrieval(branch_name: str = "CSM Training", top_k: int = RERANK_TOP_N) -> dict:
    if not os.path.exists(GOLDEN_QA_PATH):
        raise FileNotFoundError(f"Golden QA dataset not found at: {GOLDEN_QA_PATH}")

    with open(GOLDEN_QA_PATH, "r", encoding="utf-8") as f:
        qa_items = json.load(f)

    total_positive = 0
    recall_at_1_hits = 0
    recall_at_5_hits = 0
    reciprocal_ranks = []

    total_negative = 0
    rejection_hits = 0

    results_log = []

    _safe_print("\n" + "=" * 65)
    _safe_print(f"  SNOWWIKI HYBRID + CROSS-ENCODER RERANKER BENCHMARK")
    _safe_print(f"  Questions: {len(qa_items)} | Pool: {RERANK_CANDIDATE_POOL_SIZE} -> Top-K: {top_k}")
    _safe_print(f"  Calibrated Rejection Threshold: {RERANK_SCORE_THRESHOLD}")
    _safe_print("=" * 65 + "\n")

    for idx, item in enumerate(qa_items, start=1):
        qid = item["id"]
        category = item["category"]
        query = item["query"]
        expected_keywords = [k.lower() for k in item.get("expected_answer_keywords", [])]

        t0 = time.time()
        # Stage 1: Hybrid Retrieval (Dense + BM25)
        hybrid_res = hybrid_search(
            query=query,
            active_branch=branch_name,
            top_k=RERANK_CANDIDATE_POOL_SIZE,
            dense_weight=0.6,
            sparse_weight=0.4,
        )
        candidates = hybrid_res.get("fused_results", [])

        # Stage 2: Cross-Encoder Reranker (bge-reranker-base)
        top_reranked, top_score = rerank_candidates(
            query=query,
            candidates=candidates,
            top_n=top_k,
        )
        latency_ms = (time.time() - t0) * 1000.0

        if category == "negative_rejection":
            total_negative += 1
            # Passes if top rerank score is below the calibrated threshold
            passed = top_score < RERANK_SCORE_THRESHOLD
            if passed:
                rejection_hits += 1
                status = f"PASS (Gated: score={top_score:.4f} < {RERANK_SCORE_THRESHOLD})"
            else:
                status = f"FAIL (False Positive: score={top_score:.4f} >= {RERANK_SCORE_THRESHOLD})"

            _safe_print(f"[{idx:02d}/{len(qa_items):02d}] {qid} [{category}]: {status} ({latency_ms:.1f}ms)")
            results_log.append({
                "id": qid,
                "category": category,
                "query": query,
                "top_score": top_score,
                "passed": passed,
                "latency_ms": round(latency_ms, 1),
            })

        else:
            total_positive += 1
            matched_rank = None

            for rank, chunk in enumerate(top_reranked, start=1):
                doc_text = (chunk.get("document") or chunk.get("chunk_text") or "").lower()
                if any(kw in doc_text for kw in expected_keywords):
                    matched_rank = rank
                    break

            # A positive query passes if a hit occurred AND score meets threshold
            passed = (matched_rank is not None) and (top_score >= RERANK_SCORE_THRESHOLD)

            if matched_rank is not None:
                if matched_rank == 1:
                    recall_at_1_hits += 1
                recall_at_5_hits += 1
                rr = 1.0 / matched_rank
                reciprocal_ranks.append(rr)
                status = f"PASS (Hit at Rank {matched_rank} | score={top_score:.4f})"
            else:
                reciprocal_ranks.append(0.0)
                status = f"FAIL (Keywords missed | score={top_score:.4f})"

            _safe_print(f"[{idx:02d}/{len(qa_items):02d}] {qid} [{category}]: {status} ({latency_ms:.1f}ms)")
            results_log.append({
                "id": qid,
                "category": category,
                "query": query,
                "matched_rank": matched_rank,
                "top_score": top_score,
                "passed": passed,
                "latency_ms": round(latency_ms, 1),
            })

    recall_1 = (recall_at_1_hits / total_positive) if total_positive else 0.0
    recall_5 = (recall_at_5_hits / total_positive) if total_positive else 0.0
    mrr = (sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 0.0
    rejection_acc = (rejection_hits / total_negative) if total_negative else 0.0
    avg_latency = sum(r["latency_ms"] for r in results_log) / max(len(results_log), 1)

    _safe_print("\n" + "=" * 65)
    _safe_print("  HYBRID + RERANKER BENCHMARK PERFORMANCE REPORT")
    _safe_print("=" * 65)
    _safe_print(f"  Total Questions Tested      : {len(qa_items)}")
    _safe_print(f"  Positive Queries Evaluated  : {total_positive}")
    _safe_print(f"  Recall@1 (Top Rank Hit)     : {recall_1 * 100:.1f}% ({recall_at_1_hits}/{total_positive})")
    _safe_print(f"  Recall@5 (Top-5 Hit)        : {recall_5 * 100:.1f}% ({recall_at_5_hits}/{total_positive})")
    _safe_print(f"  Mean Reciprocal Rank (MRR)  : {mrr:.3f}")
    _safe_print(f"  Negative Query Rejection    : {rejection_acc * 100:.1f}% ({rejection_hits}/{total_negative})")
    _safe_print(f"  Avg Pipeline Latency        : {avg_latency:.1f} ms")
    _safe_print("=" * 65 + "\n")

    report = {
        "benchmark_file": GOLDEN_QA_PATH,
        "total_questions": len(qa_items),
        "recall_at_1": round(recall_1, 3),
        "recall_at_5": round(recall_5, 3),
        "mrr": round(mrr, 3),
        "rejection_accuracy": round(rejection_acc, 3),
        "avg_latency_ms": round(avg_latency, 1),
        "results": results_log,
    }

    report_path = os.path.join(BASE_DIR, "data", "eval", "latest_reranked_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    evaluate_reranked_retrieval()
