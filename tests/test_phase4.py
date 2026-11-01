"""
tests/test_phase4.py
====================
Unit tests for Phase 4:
  1. Audit logging & Candidate Progression Trace
  2. User feedback recording (thumbs-up / thumbs-down)
  3. Automatic hard-negative curation on downvoted/unanswered queries
"""

import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.audit_logger import build_candidate_trace, log_audit_trace, AUDIT_LOG_FILE
from src.feedback_store import (
    record_feedback,
    record_unanswered_query,
    get_feedback_metrics,
    HARD_NEGATIVES_PATH,
    FEEDBACK_LOG_PATH,
)


def test_audit_logger():
    mock_hybrid = {
        "raw_dense_hits": [
            {"id": "doc1__c0", "document": "SLA mapping doc", "metadata": {"source_file": "sla.pdf"}, "dense_rank": 1, "similarity": 0.82},
            {"id": "doc2__c1", "document": "cmn_location table", "metadata": {"source_file": "tables.docx"}, "dense_rank": 2, "similarity": 0.74},
        ],
        "raw_bm25_hits": [
            {"id": "doc2__c1", "document": "cmn_location table", "metadata": {"source_file": "tables.docx"}, "sparse_rank": 1, "bm25_score": 12.5},
        ],
        "fused_results": [
            {"id": "doc2__c1", "document": "cmn_location table", "metadata": {"source_file": "tables.docx"}, "rrf_score": 0.025},
            {"id": "doc1__c0", "document": "SLA mapping doc", "metadata": {"source_file": "sla.pdf"}, "rrf_score": 0.016},
        ],
    }
    mock_reranked = [
        {"id": "doc2__c1", "document": "cmn_location table", "metadata": {"source_file": "tables.docx"}, "rerank_score": 0.945, "rank": 1},
    ]

    trace = build_candidate_trace(
        query_id="test_qry_001",
        query_text="Where is cmn_location defined?",
        branch="CSM Training",
        hybrid_res=mock_hybrid,
        top_reranked=mock_reranked,
        top_rerank_score=0.945,
        latency_ms=145.2,
    )

    assert trace["query_id"] == "test_qry_001"
    assert trace["top_rerank_score"] == 0.945
    assert trace["gated_out"] is False
    assert len(trace["candidates_progression"]) >= 2

    # Check progression status
    c1 = next(c for c in trace["candidates_progression"] if c["chunk_id"] == "doc2__c1")
    assert "Selected" in c1["status"]
    assert c1["dense_rank"] == 2
    assert c1["sparse_rank"] == 1

    log_audit_trace(trace)
    assert os.path.exists(AUDIT_LOG_FILE)
    print("[PASS] test_audit_logger passed.")


def test_feedback_store():
    # 1. Record thumbs up
    rec1 = record_feedback(
        query_id="test_qry_001",
        query_text="How to configure SLA?",
        answer_text="Navigate to Service Level Management...",
        feedback="thumbs_up",
        branch="CSM Training",
        stage_used="🔍 Local RAG + 70B LLM",
    )
    assert rec1["feedback"] == "thumbs_up"

    # 2. Record thumbs down
    rec2 = record_feedback(
        query_id="test_qry_002",
        query_text="Explain custom script include CSMHelper",
        answer_text="CSMHelper is not documented...",
        feedback="thumbs_down",
        branch="CSM Training",
        stage_used="🔍 Local RAG + 70B LLM",
    )
    assert rec2["feedback"] == "thumbs_down"

    # Check metrics
    metrics = get_feedback_metrics("CSM Training")
    assert metrics["total_votes"] >= 2
    assert metrics["thumbs_up"] >= 1
    assert metrics["thumbs_down"] >= 1
    assert metrics["hard_negatives_count"] >= 1

    # Check hard negatives file
    assert os.path.exists(HARD_NEGATIVES_PATH)
    with open(HARD_NEGATIVES_PATH, "r", encoding="utf-8") as f:
        hn_data = json.load(f)
    assert any(item["query"] == "Explain custom script include CSMHelper" for item in hn_data)

    print("[PASS] test_feedback_store passed.")


if __name__ == "__main__":
    test_audit_logger()
    test_feedback_store()
    print("All Phase 4 unit tests passed!")
