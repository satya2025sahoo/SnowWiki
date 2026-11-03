"""
src/route_handlers/detailed_fact.py
===================================
Path D handler: Detailed Fact Parent-Child RAG with hybrid search,
cross-encoder reranking, and web fallback.
"""
from __future__ import annotations

import time
import uuid

from src.config import (
    GROQ_RESPONSE_MODEL,
    SIMILARITY_THRESHOLD,
    INSUFFICIENT_CONTEXT_MARKER,
    RERANK_SCORE_THRESHOLD,
)
from src.ingestion import get_embedder
from src.vector_store import get_vector_store
from src.llm_logger import print_terminal_context_transparency
from src.answer_generators import generate_rag_answer

from src.route_handlers.context_builder import _fetch_parent_child_context, _fetch_legacy_context
from src.route_handlers.conversation import _search_summaries
from src.route_handlers.web_fallback import _handle_web_fallback


def _handle_detailed_fact(
    query: str,
    active_branch: str,
    memory_context: dict | None,
    query_id: str | None = None,
) -> dict:
    """
    Precise fact-finding pipeline:
    1. Vector search for top-5 child chunks.
    2. Detect if branch is parent-child indexed (has parent_id in metadata).
       - If legacy: fall back to child-chunk RAG with legacy_index=True flag.
       - If new:    fetch full parent sections → pass to generation LLM.
    3. If insufficient local context → Google Search fallback.
    """
    embedder = get_embedder()
    vector_store = get_vector_store()

    running_summary = memory_context.get("running_summary", "") if memory_context else ""
    recent_turns = memory_context.get("recent_turns_text", "") if memory_context else ""

    # Enrich short follow-up queries with recent context for better vector search
    search_query = query
    if recent_turns and len(query.split()) < 5:
        search_query = f"{query} (Context: {recent_turns[-150:]})"

    query_vector = embedder.encode([search_query]).tolist()

    # ── Hybrid Search (Dense + BM25) + Cross-Encoder Reranker ───────────────
    if not query_id:
        query_id = f"qry_{uuid.uuid4().hex[:10]}"

    top_rerank_score = None
    candidate_trace = None
    t_start = time.perf_counter()
    try:
        from src.hybrid_search import hybrid_search
        from src.reranker import rerank_candidates
        from src.config import RERANK_CANDIDATE_POOL_SIZE, RERANK_TOP_N

        hybrid_res = hybrid_search(
            query=search_query,
            active_branch=active_branch,
            top_k=RERANK_CANDIDATE_POOL_SIZE,
            dense_weight=0.6,
            sparse_weight=0.4,
        )
        candidates = hybrid_res.get("fused_results", [])
        top_reranked, top_rerank_score = rerank_candidates(
            query=search_query,
            candidates=candidates,
            top_n=RERANK_TOP_N,
        )

        t_lat = (time.perf_counter() - t_start) * 1000.0
        try:
            from src.audit_logger import build_candidate_trace, log_audit_trace
            candidate_trace = build_candidate_trace(
                query_id=query_id,
                query_text=query,
                branch=active_branch,
                hybrid_res=hybrid_res,
                top_reranked=top_reranked,
                top_rerank_score=top_rerank_score,
                latency_ms=t_lat,
            )
            log_audit_trace(candidate_trace)
        except Exception as audit_exc:
            print(f"[route_handlers] Audit trace error: {audit_exc}")

        results = {
            "ids": [[c["id"] for c in top_reranked]],
            "documents": [[c["document"] for c in top_reranked]],
            "metadatas": [[c["metadata"] for c in top_reranked]],
            "distances": [[max(0.0, 1.0 - c["rerank_score"]) for c in top_reranked]],
            "raw_dense_hits": hybrid_res.get("raw_dense_hits", []),
            "raw_bm25_hits": hybrid_res.get("raw_bm25_hits", []),
            "top_rerank_score": top_rerank_score,
        }
    except Exception as exc:
        print(f"[route_handlers] Reranker / Hybrid search failed, falling back to pure dense: {exc}")
        try:
            results = vector_store.query(
                branch=active_branch,
                query_embedding=query_vector[0],
                top_k=5,
            )
            top_rerank_score = None
        except Exception:
            results = None
            top_rerank_score = None

    top_chunk = None
    top_metadata = None
    similarity = 0.0
    retrieved_chunks: list[dict] = []
    legacy_index = False
    parent_sections = []

    if results and results.get("documents") and results["documents"][0]:
        distances = results["distances"][0]
        similarity = max(0.0, 1.0 - distances[0])

        gate_threshold = RERANK_SCORE_THRESHOLD if top_rerank_score is not None else SIMILARITY_THRESHOLD
        if similarity >= gate_threshold:
            top_chunk = results["documents"][0][0]
            top_metadata = results["metadatas"][0][0]

            # ── Backwards compatibility check ────────────────────────────────
            all_metas = results["metadatas"][0]
            has_parent_id = all(
                "parent_id" in m and m.get("parent_id")
                for m in all_metas
            )
            legacy_index = not has_parent_id

            if not legacy_index:
                retrieved_chunks, context_str, parent_sections, image_manifest = _fetch_parent_child_context(
                    results, active_branch, chunk_threshold=gate_threshold, query=query
                )
            else:
                # -- Legacy path: use child chunks directly ---------------------
                print(f"[route_handlers] Legacy index detected for branch '{active_branch}'. Using child chunks.")
                retrieved_chunks, context_str = _fetch_legacy_context(results)
                image_manifest = {}
    else:
        context_str = ""
        image_manifest = {}

    summary_hints = _search_summaries(query, active_branch)

    # ── RAG path: sufficient local context ───────────────────────────────────
    if top_chunk and context_str:
        print_terminal_context_transparency(
            query=query,
            similarity=similarity,
            legacy_index=legacy_index,
            retrieved_chunks=retrieved_chunks,
            context_str=context_str,
        )

        draft, _, rag_messages = generate_rag_answer(
            query, context_str, running_summary, recent_turns, summary_hints
        )

        if INSUFFICIENT_CONTEXT_MARKER not in draft:
            return {
                "query_id":          query_id,
                "candidate_trace":   candidate_trace,
                "intent":            "SERVICENOW",
                "rag_sub_intent":    "detailed_fact",
                "route":             "local_rag",
                "badge":             "🔍 Local RAG + 70B LLM",
                "badge_class":       "badge-rag",
                "answer":            draft,
                "response":          draft,
                "found":             True,
                "source_type":       "internal",
                "similarity":        similarity,
                "stage_used":        "Path D — Parent-Child RAG" if not legacy_index else "Path D — Legacy RAG",
                "top_chunk":         top_chunk,
                "source_file":       top_metadata.get("source_file") if top_metadata else None,
                "timestamp":         top_metadata.get("timestamp") if top_metadata else None,
                "timestamp_seconds": top_metadata.get("timestamp_seconds", 0) if top_metadata else 0,
                "media_path":        top_metadata.get("media_path", "") if top_metadata else "",
                "summary_hints":     summary_hints,
                "retrieved_chunks":  retrieved_chunks,
                "legacy_index":      legacy_index,
                "image_manifest":    image_manifest,
                "_handler_trace": {
                    "stage2_retrieval": {
                        "method":              "Hybrid Search (Dense + BM25) + Cross-Encoder Reranker" if not legacy_index else "Legacy Reranker Search",
                        "similarity_score":    round(similarity, 3),
                        "rerank_score":        round(top_rerank_score, 4) if top_rerank_score is not None else round(similarity, 3),
                        "child_chunks_found":  len(retrieved_chunks),
                        "dense_matches":       len(results.get("raw_dense_hits", [])) if results else 0,
                        "bm25_matches":        len(results.get("raw_bm25_hits", [])) if results else 0,
                        "parent_ids_fetched":  list(dict.fromkeys(c.get("parent_id", "") for c in retrieved_chunks if c.get("parent_id"))),
                        "context_sent_to_llm": context_str[:1200] + " ... [truncated]" if len(context_str) > 1200 else context_str,
                    },
                    "rag_details": {
                        "mode":            "Parent-Child RAG (Path D)" if not legacy_index else "Legacy RAG (Path D)",
                        "similarity":      round(similarity, 3),
                        "child_chunks":    retrieved_chunks,
                        "parent_sections": parent_sections if not legacy_index else [],
                        "context_str":     context_str,
                    },
                    "stage2_generation": {
                        "model":        GROQ_RESPONSE_MODEL,
                        "context_sent": (context_str[:1200] + " ... [truncated]") if len(context_str) > 1200 else context_str,
                        "draft_output": draft,
                    },
                    "generation_details": {
                        "model":        GROQ_RESPONSE_MODEL,
                        "messages":     rag_messages,
                        "draft_output": draft,
                    },
                },
            }

        # Falls through — local context found but LLM couldn't answer from the extracted window
        # Return a clean insufficient-context response instead of hitting the broken Google API
        if top_chunk and retrieved_chunks:
            _ic_answer = (
                "I found relevant content in your uploaded files, but the specific detail "
                "you're asking about isn't clearly captured in the indexed sections. "
                "Try rephrasing the question or referencing the specific document/section name."
            )
            try:
                from src.feedback_store import record_unanswered_query
                record_unanswered_query(
                    query_text=query,
                    branch=active_branch,
                    reason="Insufficient local context (LLM could not extract answer from window)",
                    candidate_trace=candidate_trace,
                )
            except Exception:
                pass
            return {
                "query_id":          query_id,
                "candidate_trace":   candidate_trace,
                "intent":            "SERVICENOW",
                "rag_sub_intent":    "detailed_fact",
                "route":             "local_rag_insufficient",
                "badge":             "⚠️ Insufficient Context",
                "badge_class":       "badge-outscope",
                "answer":            _ic_answer,
                "response":          _ic_answer,
                "found":             False,
                "source_type":       "insufficient_context",
                "similarity":        similarity,
                "stage_used":        "Path D — Insufficient Context",
                "top_chunk":         top_chunk,
                "source_file":       top_metadata.get("source_file") if top_metadata else None,
                "summary_hints":     summary_hints,
                "retrieved_chunks":  retrieved_chunks,
                "legacy_index":      legacy_index,
                "image_manifest":    image_manifest,
                "_handler_trace": {
                    "retrieved_chunks":  retrieved_chunks,
                    "parent_sections":   parent_sections,
                    "image_manifest":    image_manifest,
                    "rag_details": {
                        "mode":         "Insufficient Context (local)",
                        "similarity":   round(similarity, 3),
                        "model":        GROQ_RESPONSE_MODEL,
                        "context_sent": (context_str[:1200] + " ... [truncated]") if len(context_str) > 1200 else context_str,
                        "draft_output": draft,
                    },
                    "generation_details": {
                        "model":        GROQ_RESPONSE_MODEL,
                        "messages":     rag_messages,
                        "draft_output": draft,
                    },
                },
            }

    # ── Web fallback: insufficient local context ─────────────────────────────
    try:
        from src.feedback_store import record_unanswered_query
        record_unanswered_query(
            query_text=query,
            branch=active_branch,
            reason="Insufficient local context / Web fallback",
            candidate_trace=candidate_trace,
        )
    except Exception:
        pass

    return _handle_web_fallback(query, similarity, summary_hints, legacy_index, running_summary, recent_turns)


# ── Backwards-compat shim (previously _handle_servicenow) ─────────────────────

def _handle_servicenow(
    query: str,
    active_branch: str,
    memory_context: dict | None,
    rag_sub_intent: str = "detailed_fact",
    query_id: str | None = None,
) -> dict:
    """
    Routes to global_summary or detailed_fact sub-handler based on classifier output.
    Kept as a single entry for backwards compatibility with the public API.
    """
    if not query_id:
        query_id = f"qry_{uuid.uuid4().hex[:10]}"

    if rag_sub_intent == "global_summary":
        from src.route_handlers.global_summary import _handle_global_summary
        res = _handle_global_summary(query, active_branch, memory_context)
        res["query_id"] = query_id
        return res
    return _handle_detailed_fact(query, active_branch, memory_context, query_id=query_id)
