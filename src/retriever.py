"""
src/retriever.py
================
Smart Routing Logic — 3-stage intent-aware query pipeline.

Stage 1  Intent Classifier (llama-3.1-8b-instant)
         → GREETING | SERVICENOW | OUT_OF_SCOPE

Path A   GREETING     — fast response via 8b model
Path B   OUT_OF_SCOPE — polite rejection, no LLM call
Path C   SERVICENOW   — ChromaDB RAG → 70b model
                         └→ INSUFFICIENT_CONTEXT → Google Search → 70b re-prompt

All Groq calls are made internally; callers pass no client object.
"""

from __future__ import annotations

import json
import re

import groq

from src.config import (
    GROQ_API_KEY,
    GROQ_CLASSIFIER_MODEL,
    GROQ_RESPONSE_MODEL,
    SIMILARITY_THRESHOLD,
    INSUFFICIENT_CONTEXT_MARKER,
)
from src.ingestion import get_embedder, get_chroma_collection
from src.transcriber import load_branch_state
from src.search_service import (
    google_search_servicenow,
    format_search_results_for_prompt,
)


# ── Groq client factory ────────────────────────────────────────────────────────

def _groq() -> groq.Groq:
    return groq.Groq(api_key=GROQ_API_KEY)


# ── Intent Classification ──────────────────────────────────────────────────────

_INTENT_SYSTEM = """You are an intent classifier for a ServiceNow enterprise knowledge assistant.

Classify the user message into EXACTLY one of these intents:
  - GREETING     : greetings, chit-chat, thanks, farewells, or pleasantries
  - SERVICENOW   : any question or request related to ServiceNow platform, modules,
                   configuration, workflows, scripting, ITSM, ITOM, CSM, HRSD, etc.
  - OUT_OF_SCOPE : anything not related to ServiceNow or greetings
                   (e.g. cooking, politics, general coding unrelated to ServiceNow)

Respond with ONLY valid JSON — no markdown, no explanation:
{"intent": "<GREETING|SERVICENOW|OUT_OF_SCOPE>", "confidence": <0.0-1.0>}"""


def classify_intent(query: str) -> dict:
    """
    Call llama-3.1-8b-instant to classify the user's intent.

    Returns:
        {"intent": "GREETING|SERVICENOW|OUT_OF_SCOPE", "confidence": float}
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

        if intent not in {"GREETING", "SERVICENOW", "OUT_OF_SCOPE"}:
            intent = "SERVICENOW"   # safe default

        return {"intent": intent, "confidence": confidence}

    except Exception as exc:
        print(f"[retriever] Intent classification error: {exc}")
        return {"intent": "SERVICENOW", "confidence": 0.5}   # safe fallback


# ── Path A — Greeting ──────────────────────────────────────────────────────────

def _handle_greeting(query: str, memory_context: dict) -> dict:
    """Fast greeting response via the 8b model."""
    recent = memory_context.get("recent_turns_text", "") if memory_context else ""

    messages = [
        {
            "role": "system",
            "content": (
                "You are SnowWiki, a friendly and professional AI assistant specialised in "
                "ServiceNow. Respond warmly to the user's greeting and briefly mention you "
                "can help with ServiceNow topics, training, and configuration questions."
            ),
        }
    ]
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
        "intent":      "GREETING",
        "route":       "greeting",
        "badge":       "⚡ Small LLM (Greeting)",
        "badge_class": "badge-greeting",
        "answer":      answer,
        "found":       True,
        "source_type": "greeting",
        "similarity":  1.0,
        "stage_used":  "Path A — Greeting (llama-3.1-8b-instant)",
    }


# ── Path B — Out of Scope ──────────────────────────────────────────────────────

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
        "intent":      "OUT_OF_SCOPE",
        "route":       "out_of_scope",
        "badge":       "⛔ Out of Scope",
        "badge_class": "badge-outscope",
        "answer":      answer,
        "found":       False,
        "source_type": "out_of_scope",
        "similarity":  0.0,
        "stage_used":  "Path B — Out of Scope (no LLM call)",
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


# ── Path C — ServiceNow RAG + Web Fallback ─────────────────────────────────────

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

    top_chunk    = None
    top_metadata = None
    similarity   = 0.0
    context_str  = ""

    if results and results.get("documents") and results["documents"][0]:
        distances   = results["distances"][0]
        similarity  = max(0.0, 1.0 - distances[0])

        if similarity >= SIMILARITY_THRESHOLD:
            top_chunk    = results["documents"][0][0]
            top_metadata = results["metadatas"][0][0]

            # Collect top-3 chunks for a richer context block
            context_blocks: list[str] = []
            for doc, meta in zip(results["documents"][0][:3], results["metadatas"][0][:3]):
                ts  = meta.get("timestamp", "N/A")
                src = meta.get("source_file", "Unknown")
                context_blocks.append(f"[Source: {src} | Timestamp: {ts}]\n{doc}")
            context_str = "\n\n".join(context_blocks)

    summary_hints = _search_summaries(query, active_branch)

    # ── RAG path: sufficient local context ───────────────────────────────────
    if top_chunk and context_str:
        answer, used_web = _generate_rag_answer(
            query, context_str, running_summary, recent_turns, summary_hints
        )

        if INSUFFICIENT_CONTEXT_MARKER not in answer:
            # Clean out the sentinel if the model unexpectedly echoed it partially
            return {
                "intent":        "SERVICENOW",
                "route":         "local_rag",
                "badge":         "🔍 Local RAG + 70B LLM",
                "badge_class":   "badge-rag",
                "answer":        answer,
                "found":         True,
                "source_type":   "internal",
                "similarity":    similarity,
                "stage_used":    "Path C — Local RAG (llama-3.1-8b-instant)",
                "top_chunk":     top_chunk,
                "source_file":   top_metadata.get("source_file") if top_metadata else None,
                "timestamp":     top_metadata.get("timestamp")    if top_metadata else None,
                "timestamp_seconds": top_metadata.get("timestamp_seconds", 0) if top_metadata else 0,
                "media_path":    top_metadata.get("media_path", "") if top_metadata else "",
                "summary_hints": summary_hints,
            }
        # Falls through to web fallback below

    # ── Web fallback: insufficient local context ─────────────────────────────
    web_results = google_search_servicenow(query)
    web_context = format_search_results_for_prompt(web_results)

    answer = _generate_web_answer(query, web_context, running_summary, recent_turns)

    return {
        "intent":            "SERVICENOW",
        "route":             "web_fallback",
        "badge":             "🌐 Google Search Fallback",
        "badge_class":       "badge-web",
        "answer":            answer,
        "found":             False,
        "source_type":       "web_grounding",
        "similarity":        similarity,
        "stage_used":        "Path C → Fallback (Google Search + llama-3.1-8b-instant)",
        "grounding_sources": web_results,
        "summary_hints":     summary_hints,
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
    Re-prompt llama-3.1-8b-instant with Google Search results to deliver
    a grounded web-sourced answer.
    """
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are SnowWiki, an expert ServiceNow technical architect.\n"
                "The user's question was not found in the local training knowledge base.\n"
                "Answer using the web search results provided below.\n"
                "Cite sources where relevant. Be precise and technical."
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
            temperature=0.3,
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
        return _handle_greeting(query_text, memory_context)

    if intent == "OUT_OF_SCOPE":
        return _handle_out_of_scope(query_text)

    # intent == "SERVICENOW" (also default fallback)
    return _handle_servicenow(query_text, active_branch, memory_context)
