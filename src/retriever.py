"""
src/retriever.py
================
Smart Routing Logic — 4-stage intent-aware query pipeline (v2 — Semantic Parent-Child RAG).

Stage 1  Intent Classifier (llama-3.1-8b-instant)
         → GREETING | CONVERSATIONAL | SERVICENOW | OUT_OF_SCOPE
         For SERVICENOW, also classifies rag_sub_intent:
         → global_summary | detailed_fact

Path A   GREETING        — fast response via 8b model
Path B   CONVERSATIONAL  — answers from session memory
Path C   SERVICENOW / global_summary  — answer from master summary + file topics (no vector search)
Path D   SERVICENOW / detailed_fact   — Child vector search → Parent fetch → 70b model
              └→ INSUFFICIENT_CONTEXT → Google Search → 70b re-prompt
Path E   OUT_OF_SCOPE    — polite rejection, no LLM call
"""

from __future__ import annotations

import json
import re

from src.config import (
    GROQ_CLASSIFIER_MODEL,
    GROQ_RESPONSE_MODEL,
    SIMILARITY_THRESHOLD,
    INSUFFICIENT_CONTEXT_MARKER,
)
from src.ingestion import get_embedder, get_chroma_collection, load_parent_store
from src.transcriber import load_branch_state
from src.servicenow_domain import get_classifier_domain_prompt, get_ingested_topics
from src.search_service import google_search_servicenow, format_search_results_for_prompt
from src.llm_wrapper import get_chat_client
from src.llm_logger import log_llm_interaction, print_terminal_context_transparency


# ── Groq client factory ────────────────────────────────────────────────────────

def _groq():
    return get_chat_client()


# ── Intent Classification ──────────────────────────────────────────────────────

_INTENT_SYSTEM = f"""You are an intent classifier for a ServiceNow enterprise knowledge assistant.

{get_classifier_domain_prompt()}

Classify the user message into EXACTLY one of these intents:
  - GREETING       : greetings, chit-chat, thanks, farewells, or pleasantries
  - CONVERSATIONAL : questions about the conversation itself — "what was my last question?", "can you explain that again?", "I didn't understand your reply", "repeat that", "what did you mean by X?", "what have we discussed so far?"
  - SERVICENOW     : any question or request related to ServiceNow platform, modules, configuration, workflows, scripting, ITSM, ITOM, CSM, HRSD, etc.
  - OUT_OF_SCOPE   : anything not related to ServiceNow or greetings.

For SERVICENOW intent, also classify rag_sub_intent:
  - global_summary : broad/overview queries — "Summarize the video", "List all features of X", "What topics are covered?", "Give me an overview of...", "What does this session cover?", "What can you tell me about..."
  - detailed_fact  : narrow/specific queries — "How do I set class constraints?", "What is the property name for X?", "Show me the script for Y", "Explain step 3 of the workflow", "What is the configuration for Z?"

Respond with ONLY valid JSON — no markdown, no explanation:
{{"intent": "<GREETING|CONVERSATIONAL|SERVICENOW|OUT_OF_SCOPE>", "rag_sub_intent": "<global_summary|detailed_fact>", "confidence": <0.0-1.0>}}

Note: rag_sub_intent is only meaningful when intent == SERVICENOW; for all other intents set it to "detailed_fact"."""


def classify_intent(query: str) -> dict:
    """
    Call llama-3.1-8b-instant to classify the user's intent.

    Returns:
        {
            "intent": "GREETING|CONVERSATIONAL|SERVICENOW|OUT_OF_SCOPE",
            "rag_sub_intent": "global_summary|detailed_fact",
            "confidence": float,
            "raw_output": str,          # raw JSON string from LLM (for trace)
            "system_prompt": str,       # classifier system prompt (for trace)
        }
    """
    try:
        client   = _groq()
        response = client.chat.completions.create(
            model=GROQ_CLASSIFIER_MODEL,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM},
                {"role": "user",   "content": query},
            ],
            max_tokens=80,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if the model wraps anyway
        raw_clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        data = json.loads(raw_clean)

        intent      = str(data.get("intent", "SERVICENOW")).upper()
        rag_sub     = str(data.get("rag_sub_intent", "detailed_fact")).lower()
        confidence  = float(data.get("confidence", 0.9))

        if intent not in {"GREETING", "CONVERSATIONAL", "SERVICENOW", "OUT_OF_SCOPE"}:
            intent = "SERVICENOW"
        if rag_sub not in {"global_summary", "detailed_fact"}:
            rag_sub = "detailed_fact"

        return {
            "intent": intent,
            "rag_sub_intent": rag_sub,
            "confidence": confidence,
            "raw_output": raw,
            "system_prompt": _INTENT_SYSTEM,
        }

    except Exception as exc:
        print(f"[retriever] Intent classification error: {exc}")
        return {
            "intent": "SERVICENOW",
            "rag_sub_intent": "detailed_fact",
            "confidence": 0.5,
            "raw_output": f"ERROR: {exc}",
            "system_prompt": _INTENT_SYSTEM,
        }


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
        client   = _groq()
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
        client   = _groq()
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


# ── Summary Hint Extraction ────────────────────────────────────────────────────

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
        client   = _groq()
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


# ── Path D — Detailed Fact (Parent-Child RAG) ──────────────────────────────────

def _handle_detailed_fact(
    query: str,
    active_branch: str,
    memory_context: dict | None,
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
    collection = get_chroma_collection()

    running_summary = memory_context.get("running_summary", "") if memory_context else ""
    recent_turns    = memory_context.get("recent_turns_text", "") if memory_context else ""

    # Enrich short follow-up queries with recent context for better vector search
    search_query = query
    if recent_turns and len(query.split()) < 5:
        search_query = f"{query} (Context: {recent_turns[-150:]})"

    query_vector = embedder.encode([search_query]).tolist()

    # ── ChromaDB lookup ──────────────────────────────────────────────────────
    try:
        results = collection.query(
            query_embeddings=query_vector,
            n_results=5,
            where={"branch": active_branch},
        )
    except Exception:
        results = None

    top_chunk        = None
    top_metadata     = None
    similarity       = 0.0
    retrieved_chunks: list[dict] = []
    legacy_index     = False

    if results and results.get("documents") and results["documents"][0]:
        distances  = results["distances"][0]
        similarity = max(0.0, 1.0 - distances[0])

        if similarity >= SIMILARITY_THRESHOLD:
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
                # ── New Parent-Child path ─────────────────────────────────────
                # Collect passing child chunks and their parent_ids
                child_hits: list[dict] = []
                seen_parent_ids: list[str] = []

                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    chunk_sim = max(0.0, 1.0 - dist)
                    if chunk_sim < SIMILARITY_THRESHOLD:
                        continue

                    pid = meta.get("parent_id", "")
                    ts  = meta.get("timestamp", "N/A")
                    pg  = meta.get("page", "N/A")

                    if pg != "N/A" and str(pg).strip():
                        page_or_ts = f"Page {pg}" if isinstance(pg, int) or (isinstance(pg, str) and pg.isdigit()) else str(pg)
                    elif ts != "N/A" and str(ts).strip():
                        page_or_ts = f"[{ts}]" if not str(ts).startswith("[") else str(ts)
                    else:
                        page_or_ts = "N/A"

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

                retrieved_chunks = child_hits  # child info for the UI expander

                # Fetch up to 3 unique parent sections
                parent_store    = load_parent_store(active_branch)
                parent_sections = []
                for pid in seen_parent_ids[:3]:
                    ps = parent_store.get(pid)
                    if ps:
                        parent_sections.append(ps)

                # Enrich retrieved_chunks with parent text (for the UI expander)
                for ch in retrieved_chunks:
                    pid = ch.get("parent_id", "")
                    ps  = parent_store.get(pid, {})
                    ch["parent_topic_title"] = ps.get("topic_title", ch.get("topic_title", ""))
                    ch["parent_text"]        = ps.get("content", "")

                # Build context block from full parent sections
                context_blocks: list[str] = []
                for ps in parent_sections:
                    context_blocks.append(
                        f"--- Topic: {ps['topic_title']} (Source: {ps['source']}) ---\n{ps['content']}"
                    )
                context_str = "\n\n".join(context_blocks)

            else:
                # ── Legacy path: use child chunks directly ────────────────────
                print(f"[retriever] Legacy index detected for branch '{active_branch}'. Using child chunks.")
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

                context_str = "\n\n".join(context_blocks_legacy)

    else:
        context_str = ""

    summary_hints = _search_summaries(query, active_branch)

    # ── RAG path: sufficient local context ───────────────────────────────────
    if top_chunk and context_str:
        # Context transparency terminal logging
        print_terminal_context_transparency(
            query=query,
            similarity=similarity,
            legacy_index=legacy_index,
            retrieved_chunks=retrieved_chunks,
            context_str=context_str,
        )

        draft, _, rag_messages = _generate_rag_answer(
            query, context_str, running_summary, recent_turns, summary_hints
        )

        if INSUFFICIENT_CONTEXT_MARKER not in draft:
            return {
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
                "_handler_trace": {
                    "stage2_retrieval": {
                        "method":              "Parent-Child Vector Search" if not legacy_index else "Legacy Vector Search",
                        "similarity_score":    round(similarity, 3),
                        "child_chunks_found":  len(retrieved_chunks),
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
    search_response = google_search_servicenow(query)
    status          = search_response.get("status", "ERROR")
    error_msg       = search_response.get("error_message", "")
    web_results     = search_response.get("results", [])

    if status == "DISABLED":
        answer   = (
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
        answer   = (
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
        answer   = (
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
    draft, web_messages = _generate_web_answer(query, web_context, running_summary, recent_turns)

    if draft.strip() == "NOT_FOUND" or "NOT_FOUND" in draft[:20]:
        answer   = (
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


def _generate_rag_answer(
    query: str,
    context_str: str,
    running_summary: str,
    recent_turns: str,
    summary_hints: dict,
) -> tuple[str, bool, list[dict]]:
    """
    Ask the response LLM to answer using parent section context (or legacy child chunks).
    If context is insufficient it should emit INSUFFICIENT_CONTEXT.
    Returns (answer_text, used_web_flag, messages).
    """
    master_sum = summary_hints.get("master_summary", "")

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are SnowWiki, an expert ServiceNow technical assistant.\n"
                "Answer the user's question using ONLY the provided internal knowledge base context.\n"
                "If the context does not contain enough information to answer accurately, "
                f"respond with exactly: {INSUFFICIENT_CONTEXT_MARKER}\n"
                "Do not hallucinate or invent information."
            ),
        }
    ]

    user_parts: list[str] = []

    if master_sum:
        user_parts.append(f"=== MASTER BRANCH SUMMARY ===\n{master_sum}")
    if running_summary:
        user_parts.append(f"=== CONVERSATION MEMORY ===\n{running_summary}")
    if recent_turns:
        user_parts.append(f"=== RECENT EXCHANGES ===\n{recent_turns}")

    user_parts.append(f"=== INTERNAL KNOWLEDGE BASE CONTEXT ===\n{context_str}")
    user_parts.append(f"=== USER QUESTION ===\n{query}")

    messages.append({"role": "user", "content": "\n\n".join(user_parts)})

    try:
        client   = _groq()
        response = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()
        return answer, False, messages
    except Exception as exc:
        return f"Error generating answer: {exc}", False, messages


def _generate_web_answer(
    query: str,
    web_context: str,
    running_summary: str,
    recent_turns: str,
) -> tuple[str, list[dict]]:
    """
    Re-prompt LLM with Google Search results to deliver a grounded web-sourced answer.
    Enforces strict relevance verification — emits 'NOT_FOUND' if search results are ungrounded.
    Returns (answer_text, messages).
    """
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are SnowWiki, an expert ServiceNow technical assistant.\n"
                "Answer the user's question STRICTLY AND ONLY using the web search results provided below.\n"
                "CRITICAL RELEVANCE RULE: If the search results do NOT contain direct, factual evidence to answer "
                "the question accurately, respond with EXACTLY: NOT_FOUND\n"
                "Do NOT use pre-trained internal memory to invent or fill in an answer if facts are missing from the search results.\n"
                "Cite source URLs where relevant."
            ),
        }
    ]

    user_parts: list[str] = []

    if running_summary:
        user_parts.append(f"=== CONVERSATION MEMORY ===\n{running_summary}")
    if recent_turns:
        user_parts.append(f"=== RECENT EXCHANGES ===\n{recent_turns}")

    user_parts.append(f"=== WEB SEARCH RESULTS ===\n{web_context}")
    user_parts.append(f"=== USER QUESTION ===\n{query}")

    messages.append({"role": "user", "content": "\n\n".join(user_parts)})

    try:
        client   = _groq()
        response = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip(), messages
    except Exception as exc:
        return f"Error generating web-grounded answer: {exc}", messages


# ── Backwards-compat shim (previously _handle_servicenow) ─────────────────────

def _handle_servicenow(
    query: str,
    active_branch: str,
    memory_context: dict | None,
    rag_sub_intent: str = "detailed_fact",
) -> dict:
    """
    Routes to global_summary or detailed_fact sub-handler based on classifier output.
    Kept as a single entry for backwards compatibility with the public API.
    """
    if rag_sub_intent == "global_summary":
        return _handle_global_summary(query, active_branch, memory_context)
    return _handle_detailed_fact(query, active_branch, memory_context)


# ── Public Entry Point ─────────────────────────────────────────────────────────

def query_snow_wiki(
    query_text: str,
    active_branch: str,
    memory_context: dict | None = None,
) -> dict:
    """
    Main Smart Routing entry point.

    Args:
        query_text:     The user's message.
        active_branch:  Currently selected branch / session name.
        memory_context: Dict from MemoryManager.get_condensed_context().

    Returns:
        Result dict with keys:
          intent, rag_sub_intent, route, badge, badge_class, answer, found, source_type,
          similarity, stage_used, legacy_index, pipeline_trace, and optional:
          top_chunk, source_file, timestamp, timestamp_seconds, media_path,
          grounding_sources, summary_hints, retrieved_chunks (with parent_text)
    """
    # Stage 1: Classify intent
    classification = classify_intent(query_text)
    intent         = classification["intent"]
    rag_sub_intent = classification.get("rag_sub_intent", "detailed_fact")

    classifier_trace = {
        "model":          GROQ_CLASSIFIER_MODEL,
        "user_input":     query_text,
        "system_prompt":  classification.get("system_prompt", ""),
        "raw_output":     classification.get("raw_output", ""),
        "intent":         intent,
        "rag_sub_intent": rag_sub_intent,
        "confidence":     classification.get("confidence", 0.0),
    }

    # Route based on intent
    if intent == "GREETING":
        result = _handle_greeting(query_text, active_branch, memory_context)
    elif intent == "CONVERSATIONAL":
        result = _handle_conversational(query_text, active_branch, memory_context)
    elif intent == "OUT_OF_SCOPE":
        result = _handle_out_of_scope(query_text)
    else:
        # intent == "SERVICENOW" (also default fallback)
        result = _handle_servicenow(query_text, active_branch, memory_context, rag_sub_intent)

    # Attach the classifier trace + any handler trace into pipeline_trace
    handler_trace = result.pop("_handler_trace", {})
    result["pipeline_trace"] = {
        "stage1_classifier": classifier_trace,
        **handler_trace,
    }

    # Log entire interaction to files (human-readable .log and .jsonl)
    try:
        log_llm_interaction({
            "query": query_text,
            "branch": active_branch,
            "stage_used": result.get("stage_used", ""),
            "route": result.get("route", ""),
            "classifier": classifier_trace,
            "memory": memory_context or {},
            "rag": handler_trace.get("rag_details", {}),
            "generation": handler_trace.get("generation_details", {}),
            "answer": result.get("answer", result.get("response", "")),
        })
    except Exception as log_exc:
        print(f"[retriever] Logger error: {log_exc}")

    return result
