"""
src/route_handlers.py
=====================
Path handlers for the SnowWiki 4-stage Smart Routing pipeline.

Each handler receives a query, the active branch name, and optional memory
context.  They perform retrieval (if needed) and return a standardised result
dict consumed by query_snow_wiki() in retriever.py.

Paths
-----
Path A  _handle_greeting()         — fast response via 8b model
Path B  _handle_conversational()   — answer from session memory
Path C  _handle_global_summary()   — branch overview (no vector search)
Path D  _handle_detailed_fact()    — Parent-Child RAG → web fallback
Path E  _handle_out_of_scope()     — polite rejection, no LLM call

The backwards-compat shim _handle_servicenow() is also kept here.
"""

from __future__ import annotations

from src.config import (
    GROQ_CLASSIFIER_MODEL,
    GROQ_RESPONSE_MODEL,
    SIMILARITY_THRESHOLD,
    INSUFFICIENT_CONTEXT_MARKER,
)
from src.ingestion import get_embedder, load_parent_store
from src.vector_store import get_vector_store
from src.transcriber import load_branch_state
from src.servicenow_domain import get_ingested_topics
from src.search_service import google_search_servicenow, format_search_results_for_prompt
from src.llm_wrapper import get_chat_client
from src.llm_logger import print_terminal_context_transparency
from src.answer_generators import generate_rag_answer, generate_web_answer


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _search_summaries(query: str, active_branch: str) -> dict:
    """Keyword-match file summaries to enrich prompt with context hints."""
    state          = load_branch_state(active_branch)
    master_summary = state.get("master_summary", "")
    files_dict     = state.get("files", {})
    query_lower    = query.lower()

    matching: list[dict] = []
    for fname, finfo in files_dict.items():
        f_summary = finfo.get("summary", "")
        if any(w in f_summary.lower() for w in query_lower.split() if len(w) > 3):
            matching.append(
                {"filename": fname, "summary": f_summary, "type": finfo.get("type", "file")}
            )

    return {"master_summary": master_summary, "matching_file_summaries": matching}


# ── Path A — Greeting ──────────────────────────────────────────────────────────

def _handle_greeting(query: str, active_branch: str, memory_context: dict) -> dict:
    """Fast greeting response via the 8b model, dynamically scoped."""
    recent          = memory_context.get("recent_turns_text", "") if memory_context else ""
    running_summary = memory_context.get("running_summary", "")   if memory_context else ""

    branch_state = load_branch_state(active_branch)
    topics       = get_ingested_topics(branch_state)
    topics_str   = ", ".join(topics)

    messages = [
        {
            "role": "system",
            "content": (
                "You are SnowWiki, a friendly and professional AI assistant specialised in "
                "ServiceNow.\n"
                "Respond warmly to the user's greeting and offer your assistance with ServiceNow topics."
            ),
        }
    ]
    if running_summary:
        messages.append({"role": "system", "content": f"Memory Summary: {running_summary}"})
    if recent:
        messages.append({"role": "assistant", "content": f"(Recent context)\n{recent}"})
    messages.append({"role": "user", "content": query})

    try:
        client   = get_chat_client()
        response = client.chat.completions.create(
            model=GROQ_CLASSIFIER_MODEL,
            messages=messages,
            max_tokens=256,
            temperature=0.7,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as exc:
        answer = f"Hello! I'm SnowWiki, your ServiceNow AI assistant. How can I help you today? (Error: {exc})"

    return {
        "intent":           "GREETING",
        "route":            "greeting",
        "badge":            "⚡ Small LLM (Greeting)",
        "badge_class":      "badge-greeting",
        "answer":           answer,
        "response":         answer,
        "found":            True,
        "source_type":      "greeting",
        "similarity":       1.0,
        "stage_used":       "Path A — Greeting (llama-3.1-8b-instant)",
        "retrieved_chunks": [],
        "_handler_trace": {
            "generation_details": {
                "model":        GROQ_CLASSIFIER_MODEL,
                "messages":     messages,
                "draft_output": answer,
            },
        },
    }


# ── Path B — Conversational ────────────────────────────────────────────────────

def _handle_conversational(query: str, active_branch: str, memory_context: dict | None) -> dict:
    recent          = memory_context.get("recent_turns_text", "") if memory_context else ""
    running_summary = memory_context.get("running_summary", "")   if memory_context else ""

    if not recent and not running_summary:
        answer = "We don't have any conversation history yet in this session! Please ask a ServiceNow-related question."
        return {
            "intent":           "CONVERSATIONAL",
            "route":            "conversational",
            "badge":            "💬 Conversational (Memory)",
            "badge_class":      "badge-conv",
            "answer":           answer,
            "response":         answer,
            "found":            False,
            "source_type":      "conversational",
            "similarity":       1.0,
            "stage_used":       "Path B — Conversational",
            "retrieved_chunks": [],
        }

    messages = [
        {
            "role": "system",
            "content": (
                "You are SnowWiki. The user is asking a question about your previous conversation or history.\n"
                "Answer their question accurately by referring ONLY to the conversation memory and recent exchanges provided below.\n"
                "Do not invent details outside of the provided history."
            )
        }
    ]

    user_parts = []
    if running_summary:
        user_parts.append(f"=== CONVERSATION MEMORY ===\n{running_summary}")
    if recent:
        user_parts.append(f"=== RECENT EXCHANGES ===\n{recent}")
    user_parts.append(f"=== USER QUERY ===\n{query}")

    messages.append({"role": "user", "content": "\n\n".join(user_parts)})

    try:
        client   = get_chat_client()
        response = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=messages,
            max_tokens=512,
            temperature=0.3,
        )
        draft = response.choices[0].message.content.strip()
    except Exception as exc:
        draft = f"I'm sorry, I couldn't process the conversation history. ({exc})"

    return {
        "intent":           "CONVERSATIONAL",
        "route":            "conversational",
        "badge":            "💬 Conversational (Memory)",
        "badge_class":      "badge-conv",
        "answer":           draft,
        "response":         draft,
        "found":            True,
        "source_type":      "conversational",
        "similarity":       1.0,
        "stage_used":       "Path B — Conversational",
        "retrieved_chunks": [],
        "_handler_trace": {
            "stage2_generation": {
                "model":        GROQ_RESPONSE_MODEL,
                "context_sent": "(Conversation memory + recent exchanges)",
                "draft_output": draft,
            },
            "generation_details": {
                "model":        GROQ_RESPONSE_MODEL,
                "messages":     messages,
                "draft_output": draft,
            },
        },
    }


# ── Path E — Out of Scope ──────────────────────────────────────────────────────

def _handle_out_of_scope(query: str) -> dict:
    """Return a polite rejection without any LLM call."""
    answer = (
        "I'm SnowWiki — a specialised AI assistant focused exclusively on the "
        "**ServiceNow platform**.\n\n"
        "Your question appears to be outside my area of expertise. I can help you with:\n"
        "- ServiceNow ITSM, ITOM, CSM, HRSD modules\n"
        "- Platform configuration, scripting, and workflows\n"
        "- Training knowledge from uploaded sessions\n\n"
        "Please feel free to ask a ServiceNow-related question! 🌨️"
    )
    return {
        "intent":           "OUT_OF_SCOPE",
        "route":            "out_of_scope",
        "badge":            "⛔ Out of Scope",
        "badge_class":      "badge-outscope",
        "answer":           answer,
        "response":         answer,
        "found":            False,
        "source_type":      "out_of_scope",
        "similarity":       0.0,
        "stage_used":       "Path E — Out of Scope (no LLM call)",
        "retrieved_chunks": [],
    }


# ── Path C — Global Summary (Branch Overview) ──────────────────────────────────

def _handle_global_summary(
    query: str,
    active_branch: str,
    memory_context: dict | None,
) -> dict:
    """
    Answer panoramic/overview queries directly from branch_state metadata
    (master_summary + per-file topics & summaries). No vector search performed.
    Context is capped at 12 000 chars (~3 000 tokens) to prevent context explosion.
    """
    state          = load_branch_state(active_branch)
    master_summary = state.get("master_summary", "")
    files_dict     = state.get("files", {})
    running_summary = memory_context.get("running_summary", "") if memory_context else ""
    recent_turns    = memory_context.get("recent_turns_text", "") if memory_context else ""

    # Build per-file context block (topics + summary)
    file_blocks: list[str] = []
    for fname, finfo in files_dict.items():
        topics  = finfo.get("topics", [])
        summary = finfo.get("summary", "")
        topics_str = ", ".join(topics) if topics else "N/A"
        file_blocks.append(
            f"### File: {fname}\n"
            f"**Topics:** {topics_str}\n"
            f"**Summary:** {summary}"
        )

    context_block = "\n\n".join(file_blocks)

    # Cap at ~12 000 chars to avoid context window overflow
    MAX_CONTEXT_CHARS = 12_000
    if master_summary:
        combined = f"MASTER SUMMARY:\n{master_summary}\n\n{context_block}"
    else:
        combined = context_block
    if len(combined) > MAX_CONTEXT_CHARS:
        combined = combined[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated for brevity]"

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are SnowWiki, an expert ServiceNow technical assistant.\n"
                "Answer the user's broad overview question using ONLY the branch summary context below.\n"
                "Structure your answer clearly with headings or bullet points where appropriate.\n"
                "Do not invent information not present in the context."
            ),
        }
    ]

    user_parts: list[str] = []
    if running_summary:
        user_parts.append(f"=== CONVERSATION MEMORY ===\n{running_summary}")
    if recent_turns:
        user_parts.append(f"=== RECENT EXCHANGES ===\n{recent_turns}")
    user_parts.append(f"=== BRANCH KNOWLEDGE OVERVIEW ===\n{combined}")
    user_parts.append(f"=== USER QUESTION ===\n{query}")

    messages.append({"role": "user", "content": "\n\n".join(user_parts)})

    try:
        client   = get_chat_client()
        response = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        draft = response.choices[0].message.content.strip()
    except Exception as exc:
        draft = f"Error generating overview answer: {exc}"

    return {
        "intent":           "SERVICENOW",
        "rag_sub_intent":   "global_summary",
        "route":            "global_summary",
        "badge":            "📋 Branch Overview",
        "badge_class":      "badge-overview",
        "answer":           draft,
        "response":         draft,
        "found":            True,
        "source_type":      "branch_overview",
        "similarity":       1.0,
        "stage_used":       "Path C — Global Summary (Branch Overview)",
        "retrieved_chunks": [],
        "legacy_index":     False,
        "_handler_trace": {
            "stage2_retrieval": {
                        "candidate_trace":     candidate_trace,
                "method":         "Branch Overview (no vector search)",
                "context_used":   combined[:600] + " ... [truncated]" if len(combined) > 600 else combined,
            },
            "rag_details": {
                "mode":         "Branch Overview (Path C)",
                "similarity":   1.0,
                "context_str":  combined,
            },
            "stage2_generation": {
                "model":        GROQ_RESPONSE_MODEL,
                "context_sent": combined[:1200] + " ... [truncated]" if len(combined) > 1200 else combined,
                "draft_output": draft,
            },
            "generation_details": {
                "model":        GROQ_RESPONSE_MODEL,
                "messages":     messages,
                "draft_output": draft,
            },
        },
    }


# ── Phase 4: Image manifest helpers ───────────────────────────────────────────

def resolve_image_manifest(
    image_ids: list[str],
    active_branch: str,
    max_images: int = 3,
) -> dict[str, str]:
    """
    Given a list of IMG_xxxx IDs, return {image_id: abs_path} by querying
    SQLite.  Only images that belong to `active_branch` and whose junk=0 are
    resolved.  Paths are NEVER read from LLM output — only from the DB.

    The caller is responsible for capping to `max_images` before passing IDs.
    """
    if not image_ids:
        return {}

    manifest: dict[str, str] = {}
    try:
        from src.ingestion.image_classifier import get_db_path
        import sqlite3, os as _os

        db_path = get_db_path()
        if not _os.path.exists(db_path):
            return {}

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        seen = set()
        for img_id in image_ids:
            if img_id in seen or len(manifest) >= max_images:
                break
            seen.add(img_id)

            # img_id must start with IMG_ to prevent injection
            if not img_id.startswith("IMG_"):
                continue

            cur.execute(
                """
                SELECT abs_path FROM image_assets
                WHERE image_id = ? AND branch = ? AND junk = 0
                ORDER BY created_at DESC LIMIT 1
                """,
                (img_id, active_branch),
            )
            row = cur.fetchone()
            if row:
                abs_path = row["abs_path"]
                # Path-traversal guard: must exist and be an actual file
                if abs_path and _os.path.isfile(abs_path):
                    manifest[img_id] = abs_path
        conn.close()
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("resolve_image_manifest error: %s", exc)

    return manifest


# ── Path D — Detailed Fact (Parent-Child RAG + Web Fallback) ──────────────────

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
    embedder   = get_embedder()
    vector_store = get_vector_store()

    running_summary = memory_context.get("running_summary", "") if memory_context else ""
    recent_turns    = memory_context.get("recent_turns_text", "") if memory_context else ""

    # Enrich short follow-up queries with recent context for better vector search
    search_query = query
    if recent_turns and len(query.split()) < 5:
        search_query = f"{query} (Context: {recent_turns[-150:]})"

    query_vector = embedder.encode([search_query]).tolist()

    # ── Hybrid Search (Dense + BM25) + Cross-Encoder Reranker ───────────────
    import time
    import uuid
    if not query_id:
        query_id = f"qry_{uuid.uuid4().hex[:10]}"

    top_rerank_score = None
    candidate_trace = None
    t_start = time.perf_counter()
    try:
        from src.hybrid_search import hybrid_search
        from src.reranker import rerank_candidates
        from src.config import RERANK_CANDIDATE_POOL_SIZE, RERANK_SCORE_THRESHOLD, RERANK_TOP_N

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

    top_chunk        = None
    top_metadata     = None
    similarity       = 0.0
    retrieved_chunks: list[dict] = []
    legacy_index     = False
    parent_sections  = []

    if results and results.get("documents") and results["documents"][0]:
        distances  = results["distances"][0]
        similarity = max(0.0, 1.0 - distances[0])

        gate_threshold = RERANK_SCORE_THRESHOLD if top_rerank_score is not None else SIMILARITY_THRESHOLD
        if similarity >= gate_threshold:
            top_chunk    = results["documents"][0][0]
            top_metadata = results["metadatas"][0][0]

            # ── Backwards compatibility check ────────────────────────────────
            all_metas      = results["metadatas"][0]
            has_parent_id  = all(
                "parent_id" in m and m.get("parent_id")
                for m in all_metas
            )
            legacy_index   = not has_parent_id

            if not legacy_index:
                retrieved_chunks, context_str, parent_sections, image_manifest = _fetch_parent_child_context(
                    results, active_branch
                )
            else:
                # ── Legacy path: use child chunks directly ────────────────────
                print(f"[route_handlers] Legacy index detected for branch '{active_branch}'. Using child chunks.")
                retrieved_chunks, context_str = _fetch_legacy_context(results)
                image_manifest = {}
    else:
        context_str    = ""
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
                "timestamp":         top_metadata.get("timestamp")    if top_metadata else None,
                "timestamp_seconds": top_metadata.get("timestamp_seconds", 0) if top_metadata else 0,
                "media_path":        top_metadata.get("media_path", "") if top_metadata else "",
                "summary_hints":     summary_hints,
                "retrieved_chunks":  retrieved_chunks,
                "legacy_index":      legacy_index,
                "image_manifest":    image_manifest,  # Phase 4: {image_id → abs_path}
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
                        "context_sent": context_str[:1200] + " ... [truncated]" if len(context_str) > 1200 else context_str,
                        "draft_output": draft,
                    },
                    "generation_details": {
                        "model":        GROQ_RESPONSE_MODEL,
                        "messages":     rag_messages,
                        "draft_output": draft,
                    },
                },
            }
        # Falls through to web fallback

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


def _fetch_parent_child_context(
    results: dict, active_branch: str
) -> tuple[list, str, list, dict]:
    """
    Extract parent sections from ChromaDB results.
    Returns (child_hits, context_str, parent_sections, image_manifest).

    image_manifest is a {image_id: abs_path} dict for all relevant images
    resolved securely from SQLite (never from LLM output).
    """
    child_hits: list[dict] = []
    seen_parent_ids: list[str] = []

    # ── Phase 4: Collect image IDs from all result chunks ──────────────────
    collected_image_ids: list[str] = []  # ordered, deduped later

    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunk_sim = max(0.0, 1.0 - dist)
        if chunk_sim < SIMILARITY_THRESHOLD:
            continue

        chunk_type = meta.get("chunk_type", "text")
        pid = meta.get("parent_id", "")
        ts  = meta.get("timestamp", "N/A")
        pg  = meta.get("page", "N/A")

        if pg != "N/A" and str(pg).strip():
            page_or_ts = f"Page {pg}" if isinstance(pg, int) or (isinstance(pg, str) and pg.isdigit()) else str(pg)
        elif ts != "N/A" and str(ts).strip():
            page_or_ts = f"[{ts}]" if not str(ts).startswith("[") else str(ts)
        else:
            page_or_ts = "N/A"

        # Collect image IDs: image_chunk hits carry image_id, text chunks carry image_ids
        if chunk_type == "image_chunk":
            img_id = meta.get("image_id", "")
            if img_id and img_id.startswith("IMG_") and img_id not in collected_image_ids:
                collected_image_ids.append(img_id)
            # Don't add image_chunk as a text hit — it has no prose to show
            continue

        # Regular text chunk — collect any associated image IDs
        for img_id in (meta.get("image_ids", "") or "").split(","):
            img_id = img_id.strip()
            if img_id.startswith("IMG_") and img_id not in collected_image_ids:
                collected_image_ids.append(img_id)

        child_hits.append({
            "source":            meta.get("source_file", "Unknown"),
            "parent_id":         pid,
            "topic_title":       meta.get("topic_title", ""),
            "page_or_timestamp": page_or_ts,
            "score":             round(chunk_sim, 2),
            "similarity_score":  round(chunk_sim, 2),
            "chunk_text":        doc,
        })

        if pid and pid not in seen_parent_ids:
            seen_parent_ids.append(pid)

    # ── Phase 4: Resolve image manifest (cap 3, SQLite only) ──────────────
    image_manifest = resolve_image_manifest(collected_image_ids, active_branch, max_images=3)

    # Fetch up to 3 unique parent sections
    parent_store    = load_parent_store(active_branch)
    parent_sections = []
    for pid in seen_parent_ids[:3]:
        ps = parent_store.get(pid)
        if ps:
            parent_sections.append(ps)

    # Enrich child hits with parent text (for the UI expander)
    for ch in child_hits:
        pid = ch.get("parent_id", "")
        ps  = parent_store.get(pid, {})
        ch["parent_topic_title"] = ps.get("topic_title", ch.get("topic_title", ""))
        ch["parent_text"]        = ps.get("content", "")

    # Build context block — extract a focused window around the matched child
    # chunk rather than dumping the full (potentially huge) parent section.
    MAX_CONTEXT_WINDOW = 3000   # chars (~750 tokens); keeps LLM on target

    def _extract_window(parent_content: str, child_text: str, window: int) -> str:
        """Return up to `window` chars centered on where child_text appears."""
        import re
        p_norm = parent_content.replace('\r', '')
        c_norm = child_text.replace('\r', '').strip()
        
        idx = p_norm.find(c_norm[:50])
        
        # If exact match fails, use a flexible word-based regex search
        if idx == -1:
            words = [w for w in re.split(r'\W+', c_norm) if w][:8]
            if words:
                # Find these words separated by any non-word characters (spaces, bullets, newlines)
                pattern = r'\W+'.join(words)
                match = re.search(pattern, p_norm, re.IGNORECASE)
                if match:
                    idx = match.start()
            
        if idx == -1:
            return parent_content[:window]             # fallback: head of section
            
        half  = window // 2
        start = max(0, idx - half)
        end   = min(len(parent_content), idx + half)
        prefix = "...\n" if start > 0 else ""
        suffix = "\n..." if end < len(parent_content) else ""
        return prefix + parent_content[start:end] + suffix

    # Map parent_id → the first child chunk text (for window centering)
    pid_to_child_text: dict[str, str] = {
        ch["parent_id"]: ch.get("chunk_text", "")
        for ch in reversed(child_hits)          # reversed so first hit wins
        if ch.get("parent_id")
    }

    context_blocks: list[str] = []
    for ps in parent_sections:
        pid     = ps.get("parent_id", "")
        content = ps["content"]
        if len(content) > MAX_CONTEXT_WINDOW:
            child_snippet = pid_to_child_text.get(pid, "")
            focused = _extract_window(content, child_snippet, MAX_CONTEXT_WINDOW)
        else:
            focused = content
        context_blocks.append(
            f"--- Topic: {ps['topic_title']} (Source: {ps['source']}) ---\n{focused}"
        )
    context_str = "\n\n".join(context_blocks)

    # ── Phase 4: Append image manifest block to context string ────────────
    if image_manifest:
        img_lines = []
        for img_id, abs_path in image_manifest.items():
            import os as _os
            # Only expose the filename in the context prompt — never the full path
            fname = _os.path.basename(abs_path)
            img_lines.append(f"  {img_id}: {fname}")
        context_str = (
            context_str
            + "\n\n--- Retrieved Images ---\n"
            + "\n".join(img_lines)
            + "\n\nWhen referencing an image in your answer, cite it as [IMG_xxxx]. "
            + "Do not invent image IDs not listed above."
        )

    return child_hits, context_str, parent_sections, image_manifest


def _fetch_legacy_context(results: dict) -> tuple[list, str]:
    """Build context from legacy (non-parent-child) child chunks."""
    retrieved_chunks: list[dict] = []
    context_blocks_legacy: list[str] = []

    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunk_sim = max(0.0, 1.0 - dist)
        if chunk_sim < SIMILARITY_THRESHOLD:
            continue

        ts  = meta.get("timestamp", "N/A")
        pg  = meta.get("page", "N/A")
        src = meta.get("source_file", "Unknown")

        if pg != "N/A" and str(pg).strip():
            page_or_ts = f"Page {pg}" if isinstance(pg, int) or (isinstance(pg, str) and pg.isdigit()) else str(pg)
        elif ts != "N/A" and str(ts).strip():
            page_or_ts = f"[{ts}]" if not str(ts).startswith("[") else str(ts)
        else:
            page_or_ts = "N/A"

        retrieved_chunks.append({
            "source":            src,
            "page_or_timestamp": page_or_ts,
            "score":             round(chunk_sim, 2),
            "similarity_score":  round(chunk_sim, 2),
            "chunk_text":        doc,
            "parent_id":         "",
            "topic_title":       "",
            "parent_topic_title": "",
            "parent_text":       "",
        })

        if len(context_blocks_legacy) < 3:
            context_blocks_legacy.append(f"[Source: {src} | {page_or_ts}]\n{doc}")

    return retrieved_chunks, "\n\n".join(context_blocks_legacy)


def _handle_web_fallback(
    query: str,
    similarity: float,
    summary_hints: dict,
    legacy_index: bool,
    running_summary: str,
    recent_turns: str,
) -> dict:
    """Google Search fallback when local RAG context is insufficient."""
    search_response = google_search_servicenow(query)
    status          = search_response.get("status", "ERROR")
    error_msg       = search_response.get("error_message", "")
    web_results     = search_response.get("results", [])

    if status == "DISABLED":
        answer = (
            "Web search is currently unconfigured or disabled on the server.\n\n"
            "The requested topic was not found in your uploaded session files, and web search could not be executed."
        )
        return {
            "intent":            "SERVICENOW",
            "rag_sub_intent":    "detailed_fact",
            "route":             "web_fallback_disabled",
            "badge":             "⚠️ Web Search Disabled",
            "badge_class":       "badge-outscope",
            "answer":            answer,
            "response":          answer,
            "found":             False,
            "source_type":       "web_disabled",
            "similarity":        similarity,
            "stage_used":        "Path D → Fallback (Search API Key Missing)",
            "grounding_sources": [],
            "summary_hints":     summary_hints,
            "retrieved_chunks":  [],
            "legacy_index":      legacy_index,
            "_handler_trace": {
                "stage2_retrieval": {"method": "Web Search DISABLED"},
                "rag_details": {"mode": "Web Search (Disabled)", "similarity": round(similarity, 3)},
            },
        }

    if status == "ERROR":
        answer = (
            f"Web search encountered an API error ({error_msg}).\n\n"
            "The requested topic was not found in your uploaded session files."
        )
        return {
            "intent":            "SERVICENOW",
            "rag_sub_intent":    "detailed_fact",
            "route":             "web_fallback_error",
            "badge":             "⚠️ Search Error",
            "badge_class":       "badge-outscope",
            "answer":            answer,
            "response":          answer,
            "found":             False,
            "source_type":       "web_error",
            "similarity":        similarity,
            "stage_used":        "Path D → Fallback (Search API Failure)",
            "grounding_sources": [],
            "summary_hints":     summary_hints,
            "retrieved_chunks":  [],
            "legacy_index":      legacy_index,
            "_handler_trace": {
                "stage2_retrieval": {"method": "Web Search ERROR", "error": error_msg},
                "rag_details": {"mode": "Web Search (Error)", "similarity": round(similarity, 3), "error": error_msg},
            },
        }

    if not web_results:
        answer = (
            f"I searched for **'{query}'**, but could not find relevant information "
            "in your uploaded session files or web search results."
        )
        return {
            "intent":            "SERVICENOW",
            "rag_sub_intent":    "detailed_fact",
            "route":             "web_fallback_empty",
            "badge":             "❌ Not Found in Web Search",
            "badge_class":       "badge-outscope",
            "answer":            answer,
            "response":          answer,
            "found":             False,
            "source_type":       "not_found",
            "similarity":        similarity,
            "stage_used":        "Path D → Fallback (0 Web Search Results)",
            "grounding_sources": [],
            "summary_hints":     summary_hints,
            "retrieved_chunks":  [],
            "legacy_index":      legacy_index,
            "_handler_trace": {
                "stage2_retrieval": {"method": "Web Search — 0 results returned"},
                "rag_details": {"mode": "Web Search (0 Results)", "similarity": round(similarity, 3)},
            },
        }

    web_context = format_search_results_for_prompt(web_results)
    draft, web_messages = generate_web_answer(query, web_context, running_summary, recent_turns)

    if draft.strip() == "NOT_FOUND" or "NOT_FOUND" in draft[:20]:
        answer = (
            f"I searched for **'{query}'**, but the web search results did not contain "
            "sufficient factual evidence to answer accurately."
        )
        return {
            "intent":            "SERVICENOW",
            "rag_sub_intent":    "detailed_fact",
            "route":             "web_fallback_unrelevant",
            "badge":             "❌ Not Found in Search Results",
            "badge_class":       "badge-outscope",
            "answer":            answer,
            "response":          answer,
            "found":             False,
            "source_type":       "not_found",
            "similarity":        similarity,
            "stage_used":        "Path D → Fallback (Relevance Evaluator Guardrail Reject)",
            "grounding_sources": web_results,
            "summary_hints":     summary_hints,
            "retrieved_chunks":  [],
            "legacy_index":      legacy_index,
            "_handler_trace": {
                "stage2_retrieval": {"method": "Web Search — results irrelevant (NOT_FOUND guard)"},
                "stage2_generation": {"model": GROQ_RESPONSE_MODEL, "draft_output": draft},
                "rag_details": {
                    "mode": "Web Search (Ungrounded/Irrelevant)",
                    "similarity": round(similarity, 3),
                    "web_results": web_results,
                },
                "generation_details": {
                    "model": GROQ_RESPONSE_MODEL,
                    "messages": web_messages,
                    "draft_output": draft,
                },
            },
        }

    return {
        "intent":            "SERVICENOW",
        "rag_sub_intent":    "detailed_fact",
        "route":             "web_fallback",
        "badge":             "🌐 Google Search Fallback",
        "badge_class":       "badge-web",
        "answer":            draft,
        "response":          draft,
        "found":             True,
        "source_type":       "web_grounding",
        "similarity":        similarity,
        "stage_used":        "Path D → Fallback (Google Search + Relevance Verified)",
        "grounding_sources": web_results,
        "summary_hints":     summary_hints,
        "retrieved_chunks":  [],
        "legacy_index":      legacy_index,
        "_handler_trace": {
            "stage2_retrieval": {
                "method":      "Google Search Fallback",
                "num_results": len(web_results),
                "urls":        [r.get("url", "") for r in web_results[:3]],
            },
            "rag_details": {
                "mode":        "Google Search Fallback",
                "similarity":  round(similarity, 3),
                "web_results": web_results,
            },
            "stage2_generation": {
                "model":        GROQ_RESPONSE_MODEL,
                "context_sent": web_context[:1200] + " ... [truncated]" if len(web_context) > 1200 else web_context,
                "draft_output": draft,
            },
            "generation_details": {
                "model":        GROQ_RESPONSE_MODEL,
                "messages":     web_messages,
                "draft_output": draft,
            },
        },
    }


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
    import uuid
    if not query_id:
        query_id = f"qry_{uuid.uuid4().hex[:10]}"

    if rag_sub_intent == "global_summary":
        res = _handle_global_summary(query, active_branch, memory_context)
        res["query_id"] = query_id
        return res
    return _handle_detailed_fact(query, active_branch, memory_context, query_id=query_id)
