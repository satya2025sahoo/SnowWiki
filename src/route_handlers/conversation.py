"""
src/route_handlers/conversation.py
==================================
Handlers for Path A (Greeting), Path B (Conversational memory),
Path E (Out of scope), and summary search helper.
"""
from __future__ import annotations

from src.config import (
    GROQ_CLASSIFIER_MODEL,
    GROQ_RESPONSE_MODEL,
)
from src.transcriber import load_branch_state
from src.servicenow_domain import get_ingested_topics
from src.llm_wrapper import get_chat_client


def _search_summaries(query: str, active_branch: str) -> dict:
    """Keyword-match file summaries to enrich prompt with context hints."""
    state = load_branch_state(active_branch)
    master_summary = state.get("master_summary", "")
    files_dict = state.get("files", {})
    query_lower = query.lower()

    matching: list[dict] = []
    for fname, finfo in files_dict.items():
        f_summary = finfo.get("summary", "")
        if any(w in f_summary.lower() for w in query_lower.split() if len(w) > 3):
            matching.append(
                {"filename": fname, "summary": f_summary, "type": finfo.get("type", "file")}
            )

    return {"master_summary": master_summary, "matching_file_summaries": matching}


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
        client = get_chat_client()
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


def _handle_conversational(query: str, active_branch: str, memory_context: dict | None) -> dict:
    """Answer questions about session memory or recent turns."""
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
            ),
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
        client = get_chat_client()
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
