"""
src/retriever.py
================
Smart Routing Logic — 4-stage intent-aware query pipeline.

Stage 1  Intent Classifier (llama-3.1-8b-instant)
         → GREETING | CONVERSATIONAL | SERVICENOW | OUT_OF_SCOPE

Path A   GREETING       — fast response via 8b model
Path B   CONVERSATIONAL — answers from session memory
Path C   SERVICENOW     — ChromaDB RAG → 70b model
                           └→ INSUFFICIENT_CONTEXT → Google Search → 70b re-prompt
Path D   OUT_OF_SCOPE   — polite rejection, no LLM call

Stage 3  Polish / Reply LLM
         → Refines answers from CONVERSATIONAL and SERVICENOW paths.
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
from src.ingestion import get_embedder, get_chroma_collection
from src.transcriber import load_branch_state
from src.servicenow_domain import get_classifier_domain_prompt, get_ingested_topics
from src.search_service import google_search_servicenow, format_search_results_for_prompt
from src.llm_wrapper import get_chat_client


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

Respond with ONLY valid JSON — no markdown, no explanation:
{{"intent": "<GREETING|CONVERSATIONAL|SERVICENOW|OUT_OF_SCOPE>", "confidence": <0.0-1.0>}}"""



def classify_intent(query: str) -> dict:
    """
    Call llama-3.1-8b-instant to classify the user's intent.

    Returns:
        {"intent": "GREETING|CONVERSATIONAL|SERVICENOW|OUT_OF_SCOPE", "confidence": float}
    """
    try:
        client   = _groq()
        response = client.chat.completions.create(
            model=GROQ_CLASSIFIER_MODEL,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM},
                {"role": "user",   "content": query},
            ],
            max_tokens=64,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if the model wraps anyway
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        data = json.loads(raw)

        intent     = str(data.get("intent", "SERVICENOW")).upper()
        confidence = float(data.get("confidence", 0.9))

        if intent not in {"GREETING", "CONVERSATIONAL", "SERVICENOW", "OUT_OF_SCOPE"}:
            intent = "SERVICENOW"   # safe default

        return {"intent": intent, "confidence": confidence}

    except Exception as exc:
        print(f"[retriever] Intent classification error: {exc}")
        return {"intent": "SERVICENOW", "confidence": 0.5}   # safe fallback


# ── Stage 3 — Polish LLM ───────────────────────────────────────────────────────

def _polish_answer(query: str, draft_answer: str, memory_context: dict | None) -> str:
    """
    Refines and polishes a draft answer using a small fast LLM.
    """
    if INSUFFICIENT_CONTEXT_MARKER in draft_answer or "NOT_FOUND" in draft_answer[:20]:
        return "__NO_ANSWER__"

    recent = memory_context.get("recent_turns_text", "") if memory_context else ""
    running_summary = memory_context.get("running_summary", "") if memory_context else ""

    system_prompt = (
        "You are SnowWiki's response refiner. You receive a draft answer and improve it:\n"
        " - Fix structure and formatting (use bullet points / headers where helpful)\n"
        " - Make it more natural and readable\n"
        " - If the draft says INSUFFICIENT_CONTEXT or NOT_FOUND -> return exactly: __NO_ANSWER__\n"
        " - Keep all factual content unchanged — do NOT add new facts"
    )

    user_parts = []
    if running_summary:
        user_parts.append(f"=== CONVERSATION MEMORY ===\n{running_summary}")
    if recent:
        user_parts.append(f"=== RECENT EXCHANGES ===\n{recent}")
    user_parts.append(f"=== USER QUERY ===\n{query}")
    user_parts.append(f"=== DRAFT ANSWER ===\n{draft_answer}")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(user_parts)}
    ]

    try:
        client = _groq()
        response = client.chat.completions.create(
            model=GROQ_CLASSIFIER_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        polished = response.choices[0].message.content.strip()
        if polished == "__NO_ANSWER__":
            return draft_answer
        return polished
    except Exception as exc:
        print(f"[retriever] Polish error: {exc}")
        return draft_answer


# ── Path A — Greeting ──────────────────────────────────────────────────────────

def _handle_greeting(query: str, active_branch: str, memory_context: dict) -> dict:
    """Fast greeting response via the 8b model, dynamically scoped."""
    recent = memory_context.get("recent_turns_text", "") if memory_context else ""
    running_summary = memory_context.get("running_summary", "") if memory_context else ""
    
    branch_state = load_branch_state(active_branch)
    topics = get_ingested_topics(branch_state)
    topics_str = ", ".join(topics)

    messages = [
        {
            "role": "system",
            "content": (
                "You are SnowWiki, a friendly and professional AI assistant specialised in "
                "ServiceNow.\n"
                f"You can help with topics from the user's uploaded training: **{topics_str}**.\n"
                "Respond warmly to the user's greeting and briefly mention exactly what topics you can help with based on the list above."
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
        answer = f"Hello! I'm SnowWiki, your ServiceNow AI assistant. I can help with topics like {topics_str}. How can I help you today? (Error: {exc})"

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
    }


# ── Path B — Conversational ────────────────────────────────────────────────────

def _handle_conversational(query: str, active_branch: str, memory_context: dict | None) -> dict:
    recent = memory_context.get("recent_turns_text", "") if memory_context else ""
    running_summary = memory_context.get("running_summary", "") if memory_context else ""
    
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
        client = _groq()
        response = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=messages,
            max_tokens=512,
            temperature=0.3,
        )
        draft = response.choices[0].message.content.strip()
    except Exception as exc:
        draft = f"I'm sorry, I couldn't process the conversation history. ({exc})"
        
    polished = _polish_answer(query, draft, memory_context)
    
    return {
        "intent":           "CONVERSATIONAL",
        "route":            "conversational",
        "badge":            "💬 Conversational (Memory)",
        "badge_class":      "badge-conv",
        "answer":           polished,
        "response":         polished,
        "found":            True,
        "source_type":      "conversational",
        "similarity":       1.0,
        "stage_used":       "Path B — Conversational + Polish",
        "retrieved_chunks": [],
    }

# ── Path C — Out of Scope ──────────────────────────────────────────────────────

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
        "stage_used":       "Path C — Out of Scope (no LLM call)",
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


# ── Path D — ServiceNow RAG + Web Fallback ─────────────────────────────────────

def _handle_servicenow(
    query: str,
    active_branch: str,
    memory_context: dict | None,
) -> dict:
    """
    Full ServiceNow handling pipeline:
    1. ChromaDB vector search
    2. If hit  → llama-3.1-8b-instant with context
    3. If miss or INSUFFICIENT_CONTEXT → Google Custom Search → 70b re-prompt
    """
    embedder   = get_embedder()
    collection = get_chroma_collection()

    running_summary  = memory_context.get("running_summary", "")  if memory_context else ""
    recent_turns     = memory_context.get("recent_turns_text", "") if memory_context else ""

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
    context_str      = ""
    retrieved_chunks: list[dict] = []

    if results and results.get("documents") and results["documents"][0]:
        distances  = results["distances"][0]
        similarity = max(0.0, 1.0 - distances[0])

        if similarity >= SIMILARITY_THRESHOLD:
            top_chunk    = results["documents"][0][0]
            top_metadata = results["metadatas"][0][0]

            # Collect vector chunks that meet similarity threshold
            context_blocks: list[str] = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                chunk_sim = max(0.0, 1.0 - dist)
                if chunk_sim >= SIMILARITY_THRESHOLD:
                    ts  = meta.get("timestamp", "N/A")
                    pg  = meta.get("page", "N/A")
                    src = meta.get("source_file", "Unknown")

                    if pg != "N/A" and str(pg).strip():
                        page_or_ts = f"Page {pg}" if isinstance(pg, int) or (isinstance(pg, str) and pg.isdigit()) else str(pg)
                    elif ts != "N/A" and str(ts).strip():
                        page_or_ts = f"[{ts}]" if not str(ts).startswith("[") else str(ts)
                    else:
                        page_or_ts = "N/A"

                    chunk_info = {
                        "source":            src,
                        "page":              pg,
                        "timestamp":         ts,
                        "page_or_timestamp": page_or_ts,
                        "score":             round(chunk_sim, 2),
                        "similarity_score":  round(chunk_sim, 2),
                        "chunk_text":        doc,
                    }
                    retrieved_chunks.append(chunk_info)
                    if len(context_blocks) < 3:
                        context_blocks.append(f"[Source: {src} | Page/Time: {page_or_ts}]\n{doc}")

            context_str = "\n\n".join(context_blocks)

    summary_hints = _search_summaries(query, active_branch)

    # ── RAG path: sufficient local context ───────────────────────────────────
    if top_chunk and context_str:
        draft, used_web = _generate_rag_answer(
            query, context_str, running_summary, recent_turns, summary_hints
        )

        if INSUFFICIENT_CONTEXT_MARKER not in draft:
            polished = _polish_answer(query, draft, memory_context)
            return {
                "intent":            "SERVICENOW",
                "route":             "local_rag",
                "badge":             "🔍 Local RAG + 70B LLM",
                "badge_class":       "badge-rag",
                "answer":            polished,
                "response":          polished,
                "found":             True,
                "source_type":       "internal",
                "similarity":        similarity,
                "stage_used":        "Path D — Local RAG + Polish",
                "top_chunk":         top_chunk,
                "source_file":       top_metadata.get("source_file") if top_metadata else None,
                "timestamp":         top_metadata.get("timestamp")    if top_metadata else None,
                "timestamp_seconds": top_metadata.get("timestamp_seconds", 0) if top_metadata else 0,
                "media_path":        top_metadata.get("media_path", "") if top_metadata else "",
                "summary_hints":     summary_hints,
                "retrieved_chunks":  retrieved_chunks,
            }
        # Falls through to web fallback below

    # ── Web fallback: insufficient local context ─────────────────────────────
    search_response = google_search_servicenow(query)
    status          = search_response.get("status", "ERROR")
    error_msg       = search_response.get("error_message", "")
    web_results     = search_response.get("results", [])

    if status == "DISABLED":
        answer = (
            "Web search is currently unconfigured or disabled on the server.\n\n"
            "The requested topic was not found in your uploaded session files, and web search could not be executed."
        )
        polished = _polish_answer(query, answer, memory_context)
        return {
            "intent":            "SERVICENOW",
            "route":             "web_fallback_disabled",
            "badge":             "⚠️ Web Search Disabled",
            "badge_class":       "badge-outscope",
            "answer":            polished,
            "response":          polished,
            "found":             False,
            "source_type":       "web_disabled",
            "similarity":        similarity,
            "stage_used":        "Path D → Fallback (Search API Key Missing)",
            "grounding_sources": [],
            "summary_hints":     summary_hints,
            "retrieved_chunks":  [],
        }

    if status == "ERROR":
        answer = (
            f"Web search encountered an API error ({error_msg}).\n\n"
            "The requested topic was not found in your uploaded session files."
        )
        polished = _polish_answer(query, answer, memory_context)
        return {
            "intent":            "SERVICENOW",
            "route":             "web_fallback_error",
            "badge":             "⚠️ Search Error",
            "badge_class":       "badge-outscope",
            "answer":            polished,
            "response":          polished,
            "found":             False,
            "source_type":       "web_error",
            "similarity":        similarity,
            "stage_used":        "Path D → Fallback (Search API Failure)",
            "grounding_sources": [],
            "summary_hints":     summary_hints,
            "retrieved_chunks":  [],
        }

    if not web_results:
        answer = (
            f"I searched for **'{query}'**, but could not find relevant information "
            "in your uploaded session files or web search results."
        )
        polished = _polish_answer(query, answer, memory_context)
        return {
            "intent":            "SERVICENOW",
            "route":             "web_fallback_empty",
            "badge":             "❌ Not Found in Web Search",
            "badge_class":       "badge-outscope",
            "answer":            polished,
            "response":          polished,
            "found":             False,
            "source_type":       "not_found",
            "similarity":        similarity,
            "stage_used":        "Path D → Fallback (0 Web Search Results)",
            "grounding_sources": [],
            "summary_hints":     summary_hints,
            "retrieved_chunks":  [],
        }

    web_context = format_search_results_for_prompt(web_results)
    draft       = _generate_web_answer(query, web_context, running_summary, recent_turns)

    if draft.strip() == "NOT_FOUND" or "NOT_FOUND" in draft[:20]:
        answer = (
            f"I searched for **'{query}'**, but the web search results did not contain "
            "sufficient factual evidence to answer accurately."
        )
        polished = _polish_answer(query, answer, memory_context)
        return {
            "intent":            "SERVICENOW",
            "route":             "web_fallback_unrelevant",
            "badge":             "❌ Not Found in Search Results",
            "badge_class":       "badge-outscope",
            "answer":            polished,
            "response":          polished,
            "found":             False,
            "source_type":       "not_found",
            "similarity":        similarity,
            "stage_used":        "Path D → Fallback (Relevance Evaluator Guardrail Reject)",
            "grounding_sources": web_results,
            "summary_hints":     summary_hints,
            "retrieved_chunks":  [],
        }

    polished = _polish_answer(query, draft, memory_context)
    return {
        "intent":            "SERVICENOW",
        "route":             "web_fallback",
        "badge":             "🌐 Google Search Fallback",
        "badge_class":       "badge-web",
        "answer":            polished,
        "response":          polished,
        "found":             True,
        "source_type":       "web_grounding",
        "similarity":        similarity,
        "stage_used":        "Path D → Fallback (Google Search + Relevance Verified) + Polish",
        "grounding_sources": web_results,
        "summary_hints":     summary_hints,
        "retrieved_chunks":  [],
    }


def _generate_rag_answer(
    query: str,
    context_str: str,
    running_summary: str,
    recent_turns: str,
    summary_hints: dict,
) -> tuple[str, bool]:
    """
    Ask llama-3.1-8b-instant to answer using local RAG context.
    If context is insufficient it should emit INSUFFICIENT_CONTEXT.
    Returns (answer_text, used_web_flag).
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
        return answer, False
    except Exception as exc:
        return f"Error generating answer: {exc}", False


def _generate_web_answer(
    query: str,
    web_context: str,
    running_summary: str,
    recent_turns: str,
) -> str:
    """
    Re-prompt LLM with Google Search results to deliver a grounded web-sourced answer.
    Enforces strict relevance verification — emits 'NOT_FOUND' if search results are ungrounded.
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
        return response.choices[0].message.content.strip()
    except Exception as exc:
        return f"Error generating web-grounded answer: {exc}"



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
          intent, route, badge, badge_class, answer, found, source_type,
          similarity, stage_used, and optional:
          top_chunk, source_file, timestamp, timestamp_seconds, media_path,
          grounding_sources, summary_hints
    """
    # Stage 1: Classify intent
    classification = classify_intent(query_text)
    intent         = classification["intent"]

    # Route based on intent
    if intent == "GREETING":
        return _handle_greeting(query_text, active_branch, memory_context)

    if intent == "CONVERSATIONAL":
        return _handle_conversational(query_text, active_branch, memory_context)

    if intent == "OUT_OF_SCOPE":
        return _handle_out_of_scope(query_text)

    # intent == "SERVICENOW" (also default fallback)
    return _handle_servicenow(query_text, active_branch, memory_context)
