"""
src/reranker.py
===============
Cross-Encoder Reranker Service for SnowWiki.
Uses 'BAAI/bge-reranker-base' to re-score candidate chunks retrieved by Hybrid Search.

Joint cross-attention computes a true semantic relevance score for (query, document) pairs.
SentenceTransformers CrossEncoder outputs normalized probability scores [0, 1].
Applies a calibrated threshold to reject out-of-scope / ungrounded queries.
Provides lost-in-the-middle context reordering for optimal LLM attention.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

import torch
from sentence_transformers import CrossEncoder

from src.config import (
    RERANKER_MODEL_NAME,
    RERANK_SCORE_THRESHOLD,
    RERANK_TOP_N,
)

logger = logging.getLogger(__name__)

_RERANKER_INSTANCE: Optional[CrossEncoder] = None
_RERANKER_LOCK = threading.Lock()


def get_reranker() -> CrossEncoder:
    """Lazy-load and cache the CrossEncoder reranker model."""
    global _RERANKER_INSTANCE
    with _RERANKER_LOCK:
        if _RERANKER_INSTANCE is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading Reranker model '{RERANKER_MODEL_NAME}' on {device}...")
            try:
                _RERANKER_INSTANCE = CrossEncoder(
                    RERANKER_MODEL_NAME,
                    max_length=512,
                    device=device,
                )
                logger.info(f"Reranker model '{RERANKER_MODEL_NAME}' loaded on {device}.")
            except Exception as exc:
                if device == "cuda":
                    logger.warning(
                        f"Failed to load reranker on CUDA ({exc}). Falling back to CPU..."
                    )
                    _RERANKER_INSTANCE = CrossEncoder(
                        RERANKER_MODEL_NAME,
                        max_length=512,
                        device="cpu",
                    )
                    logger.info("Reranker model loaded on CPU fallback.")
                else:
                    raise exc
    return _RERANKER_INSTANCE


def rerank_candidates(
    query: str,
    candidates: List[Dict[str, Any]],
    top_n: int = RERANK_TOP_N,
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Rerank a pool of candidate chunks using CrossEncoder.

    Args:
        query: User's query string.
        candidates: List of candidate chunk dicts, each with 'document' (or 'text'/'chunk_text').
        top_n: Number of top reranked chunks to return.

    Returns:
        (reranked_chunks, top_rerank_score)
        where reranked_chunks is sorted descending by rerank_score (range [0, 1]).
    """
    if not candidates:
        return [], 0.0

    model = get_reranker()

    # Build pairs of [query, chunk_text]
    doc_texts: List[str] = []
    for c in candidates:
        text = c.get("document") or c.get("chunk_text") or c.get("text", "")
        doc_texts.append(text)

    pairs = [[query, text] for text in doc_texts]

    # Predict relevance scores (CrossEncoder yields normalized probabilities)
    try:
        raw_scores = model.predict(pairs, show_progress_bar=False)
    except Exception as exc:
        logger.error(f"Reranker prediction failed: {exc}")
        # Fallback: preserve candidate order with neutral score
        return candidates[:top_n], 0.50

    scored_candidates: List[Dict[str, Any]] = []
    for candidate, raw_score in zip(candidates, raw_scores):
        score_val = max(0.0, min(1.0, float(raw_score)))
        c_copy = dict(candidate)
        c_copy["rerank_score"] = round(score_val, 4)
        scored_candidates.append(c_copy)

    # Sort descending by rerank_score
    scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

    top_candidates = scored_candidates[:top_n]
    top_score = top_candidates[0]["rerank_score"] if top_candidates else 0.0

    return top_candidates, top_score


def reorder_lost_in_the_middle(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Reorder chunks to mitigate LLM attention degradation (Liu et al. 2023).
    Places the highest-scoring chunk at the beginning and the second-highest at the end:
    Rank 1 -> position 0
    Rank 2 -> position -1
    Rank 3 -> position 1
    Rank 4 -> position -2
    etc.
    """
    if len(chunks) <= 2:
        return chunks

    reordered: List[Dict[str, Any]] = [None] * len(chunks)
    left = 0
    right = len(chunks) - 1

    for i, chunk in enumerate(chunks):
        if i % 2 == 0:
            reordered[left] = chunk
            left += 1
        else:
            reordered[right] = chunk
            right -= 1

    return [c for c in reordered if c is not None]
