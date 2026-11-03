"""
src/feedback_store.py
=====================
User Feedback & Hard-Negative Active Learning Loop for SnowWiki.

Captures:
  1. Thumbs-up / Thumbs-down rating on assistant responses.
  2. Automatic extraction of downvoted queries or out-of-scope/unanswered queries
     into `data/eval/hard_negatives.json` to expand golden test coverage.
  3. Feedback analytics (satisfaction rate, total votes, problem query list).
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

EVAL_DIR = os.path.join(DATA_DIR, "eval")
FEEDBACK_LOG_PATH = os.path.join(EVAL_DIR, "user_feedback.jsonl")
HARD_NEGATIVES_PATH = os.path.join(EVAL_DIR, "hard_negatives.json")


def _ensure_dir() -> None:
    os.makedirs(EVAL_DIR, exist_ok=True)


def record_feedback(
    query_id: str,
    query_text: str,
    answer_text: str,
    feedback: str,  # "thumbs_up" | "thumbs_down"
    branch: str,
    stage_used: str = "",
    top_rerank_score: Optional[float] = None,
    candidate_trace: Optional[Dict[str, Any]] = None,
    user_comment: str = "",
) -> Dict[str, Any]:
    """
    Save user feedback (thumbs up / thumbs down) for a specific query response.
    If thumbs_down, automatically enqueue to hard_negatives.json.
    """
    _ensure_dir()
    timestamp = datetime.datetime.now().isoformat()
    record = {
        "query_id": query_id,
        "timestamp": timestamp,
        "query": query_text,
        "answer_preview": answer_text[:200].strip().replace("\n", " "),
        "feedback": feedback,
        "branch": branch,
        "stage_used": stage_used,
        "top_rerank_score": top_rerank_score,
        "user_comment": user_comment,
    }

    # 1. Append to user_feedback.jsonl
    try:
        with open(FEEDBACK_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning(f"Failed to record feedback to {FEEDBACK_LOG_PATH}: {exc}")

    # 2. If downvoted, curate into hard_negatives.json
    if feedback == "thumbs_down":
        _add_to_hard_negatives(
            query=query_text,
            branch=branch,
            answer=answer_text,
            reason="User downvoted response",
            candidate_trace=candidate_trace,
        )

    return record


def record_unanswered_query(
    query_text: str,
    branch: str,
    reason: str = "Insufficient local context / Web fallback",
    candidate_trace: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Automatically record queries that failed RAG threshold gating into hard_negatives.json
    so content curators know what knowledge gaps exist.
    """
    _add_to_hard_negatives(
        query=query_text,
        branch=branch,
        answer="",
        reason=reason,
        candidate_trace=candidate_trace,
    )


def _add_to_hard_negatives(
    query: str,
    branch: str,
    answer: str = "",
    reason: str = "",
    candidate_trace: Optional[Dict[str, Any]] = None,
) -> None:
    """Internal helper to append a hard negative without duplicating queries."""
    _ensure_dir()
    negatives: List[Dict[str, Any]] = []
    if os.path.exists(HARD_NEGATIVES_PATH):
        try:
            with open(HARD_NEGATIVES_PATH, "r", encoding="utf-8") as f:
                negatives = json.load(f)
        except Exception:
            negatives = []

    # Check for existing query
    clean_q = query.strip().lower()
    for item in negatives:
        if item.get("query", "").strip().lower() == clean_q and item.get("branch") == branch:
            # Already tracked — update timestamp and count
            item["last_seen"] = datetime.datetime.now().isoformat()
            item["count"] = item.get("count", 1) + 1
            break
    else:
        negatives.append({
            "id": f"hn_{len(negatives) + 1:03d}",
            "query": query,
            "branch": branch,
            "reason": reason,
            "sample_answer": answer[:200] if answer else "",
            "created_at": datetime.datetime.now().isoformat(),
            "last_seen": datetime.datetime.now().isoformat(),
            "count": 1,
            "top_candidates": [
                {
                    "chunk_id": c.get("chunk_id"),
                    "source_file": c.get("source_file"),
                    "rerank_score": c.get("rerank_score"),
                    "snippet": c.get("snippet"),
                }
                for c in (candidate_trace.get("candidates_progression", [])[:3] if candidate_trace else [])
            ],
        })

    try:
        with open(HARD_NEGATIVES_PATH, "w", encoding="utf-8") as f:
            json.dump(negatives, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning(f"Failed to save hard negative to {HARD_NEGATIVES_PATH}: {exc}")


def get_feedback_metrics(branch: Optional[str] = None) -> Dict[str, Any]:
    """Calculate feedback KPIs for dashboard observability."""
    if not os.path.exists(FEEDBACK_LOG_PATH):
        return {
            "total_votes": 0,
            "thumbs_up": 0,
            "thumbs_down": 0,
            "satisfaction_rate": 0.0,
            "hard_negatives_count": 0,
        }

    total = 0
    up = 0
    down = 0

    try:
        with open(FEEDBACK_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if branch and item.get("branch") != branch:
                    continue
                total += 1
                if item.get("feedback") == "thumbs_up":
                    up += 1
                elif item.get("feedback") == "thumbs_down":
                    down += 1
    except Exception:
        pass

    hn_count = 0
    if os.path.exists(HARD_NEGATIVES_PATH):
        try:
            with open(HARD_NEGATIVES_PATH, "r", encoding="utf-8") as f:
                hn_data = json.load(f)
                hn_count = len(hn_data) if isinstance(hn_data, list) else 0
        except Exception:
            pass

    rate = round((up / total * 100), 1) if total > 0 else 0.0
    return {
        "total_votes": total,
        "thumbs_up": up,
        "thumbs_down": down,
        "satisfaction_rate": rate,
        "hard_negatives_count": hn_count,
    }
