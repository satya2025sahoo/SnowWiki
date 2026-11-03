"""
src/route_handlers/global_summary.py
====================================
Path C handler: Panoramic/overview queries answered from branch_state metadata
(master_summary + per-file topics & summaries).
"""
from __future__ import annotations

from src.config import GROQ_RESPONSE_MODEL
from src.transcriber import load_branch_state
from src.llm_wrapper import get_chat_client


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
    state = load_branch_state(active_branch)
    master_summary = state.get("master_summary", "")
    files_dict = state.get("files", {})
    running_summary = memory_context.get("running_summary", "") if memory_context else ""
    recent_turns = memory_context.get("recent_turns_text", "") if memory_context else ""

    # Build per-file context block (topics + summary)
    file_blocks: list[str] = []
    for fname, finfo in files_dict.items():
        topics = finfo.get("topics", [])
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
        client = get_chat_client()
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
                "candidate_trace": None,
                "method":          "Branch Overview (no vector search)",
                "context_used":    combined[:600] + " ... [truncated]" if len(combined) > 600 else combined,
            },
            "rag_details": {
                "mode":        "Branch Overview (Path C)",
                "similarity":  1.0,
                "context_str": combined,
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
