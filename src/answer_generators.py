"""
src/answer_generators.py
========================
LLM answer-generation helpers for the SnowWiki Smart Routing pipeline.

These functions receive pre-built context strings and call the Groq response
model to produce a final answer.  They are intentionally free of retrieval
logic — retrieval lives in route_handlers.py.

Public API
----------
generate_rag_answer(query, context_str, running_summary, recent_turns, summary_hints)
    -> tuple[str, bool, list[dict]]

generate_web_answer(query, web_context, running_summary, recent_turns)
    -> tuple[str, list[dict]]
"""

from __future__ import annotations

from src.config import GROQ_RESPONSE_MODEL, INSUFFICIENT_CONTEXT_MARKER
from src.llm_wrapper import get_chat_client


# ── RAG Answer (internal knowledge base) ──────────────────────────────────────

def generate_rag_answer(
    query: str,
    context_str: str,
    running_summary: str,
    recent_turns: str,
    summary_hints: dict,
) -> tuple[str, bool, list[dict]]:
    """
    Ask the response LLM to answer using parent-section context (or legacy child chunks).

    If context is insufficient the model is instructed to emit INSUFFICIENT_CONTEXT.

    Returns:
        (answer_text, used_web_flag, messages_sent)
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
        client   = get_chat_client()
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


# ── Web-Grounded Answer (Google Search fallback) ───────────────────────────────

def generate_web_answer(
    query: str,
    web_context: str,
    running_summary: str,
    recent_turns: str,
) -> tuple[str, list[dict]]:
    """
    Re-prompt the LLM with Google Search results to deliver a grounded web-sourced answer.

    Enforces strict relevance verification — emits 'NOT_FOUND' if search results are
    ungrounded relative to the query.

    Returns:
        (answer_text, messages_sent)
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
        client   = get_chat_client()
        response = client.chat.completions.create(
            model=GROQ_RESPONSE_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip(), messages
    except Exception as exc:
        return f"Error generating web-grounded answer: {exc}", messages
