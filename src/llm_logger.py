"""
src/llm_logger.py
=================
Structured logging module for SnowWiki LLM interactions.
Provides context transparency by logging:
  - User Query and Session context
  - Memory Context (Running summary + recent turns)
  - Intent Classifier prompt, raw output, and parsed intent
  - RAG Retrieval results (Matched child chunks, scores, source files, and expanded parent sections)
  - Exact messages/context sent to the generation LLM
  - Generated LLM output

Logs are saved to:
  - `logs/llm_context.log` (human-readable formatted trace)
  - `logs/llm_interactions.jsonl` (structured machine-readable JSON lines)
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

from src.config import LOGS_DIR

HUMAN_LOG_FILE = os.path.join(LOGS_DIR, "llm_context.log")
JSONL_LOG_FILE = os.path.join(LOGS_DIR, "llm_interactions.jsonl")


def _format_divider(title: str = "", width: int = 70, char: str = "=") -> str:
    if not title:
        return char * width
    prefix = f"{char * 3} {title} "
    return prefix + char * max(0, width - len(prefix))


def log_llm_interaction(trace_data: dict[str, Any]) -> None:
    """
    Log an entire query lifecycle to both human-readable log and jsonl log files.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trace_data_with_ts = {"timestamp": timestamp, **trace_data}

    # ── 1. Append JSONL Entry ──────────────────────────────────────────────────
    try:
        with open(JSONL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_data_with_ts, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[llm_logger] Failed to write to {JSONL_LOG_FILE}: {exc}")

    # ── 2. Append Human-Readable Entry ─────────────────────────────────────────
    try:
        lines: list[str] = []
        lines.append("\n" + _format_divider(f"QUERY TRACE [{timestamp}]", 80, "="))
        lines.append(f"📌 User Query    : {trace_data.get('query', 'N/A')}")
        lines.append(f"🌿 Active Branch : {trace_data.get('branch', 'N/A')}")
        lines.append(f"🎯 Route / Stage : {trace_data.get('stage_used', trace_data.get('route', 'N/A'))}")

        # Intent classification block
        classifier = trace_data.get("classifier", {})
        if classifier:
            lines.append("\n" + _format_divider("1. INTENT CLASSIFICATION", 60, "-"))
            lines.append(f"Model       : {classifier.get('model', 'N/A')}")
            lines.append(f"Intent      : {classifier.get('intent', 'N/A')} (rag_sub_intent: {classifier.get('rag_sub_intent', 'N/A')})")
            lines.append(f"Confidence  : {classifier.get('confidence', 'N/A')}")
            if "raw_output" in classifier:
                lines.append(f"Raw Output  : {classifier.get('raw_output')}")

        # Memory Context
        memory = trace_data.get("memory", {})
        if memory:
            lines.append("\n" + _format_divider("2. CONVERSATION MEMORY CONTEXT", 60, "-"))
            summary = memory.get("running_summary", "").strip()
            recent = memory.get("recent_turns_text", "").strip()
            lines.append(f"Running Summary:\n{summary if summary else '(None)'}\n")
            lines.append(f"Recent Turns:\n{recent if recent else '(None)'}")

        # RAG Retrieval details
        rag = trace_data.get("rag", {})
        if rag:
            lines.append("\n" + _format_divider("3. RAG RETRIEVAL & CONTEXT EXPANSION", 60, "-"))
            lines.append(f"Mode              : {rag.get('mode', 'N/A')}")
            lines.append(f"Top Similarity    : {rag.get('similarity', 'N/A')}")

            child_chunks = rag.get("child_chunks", [])
            if child_chunks:
                lines.append(f"\n--- Matched Child Chunks ({len(child_chunks)} retrieved) ---")
                for i, chunk in enumerate(child_chunks, 1):
                    score = chunk.get("similarity_score", chunk.get("score", "N/A"))
                    src = chunk.get("source", "Unknown")
                    pos = chunk.get("page_or_timestamp", "N/A")
                    txt = chunk.get("chunk_text", "").strip()
                    lines.append(f"\n[Chunk #{i} | Score: {score} | Source: {src} | Pos: {pos}]")
                    lines.append(txt)

            parent_sections = rag.get("parent_sections", [])
            if parent_sections:
                lines.append(f"\n--- Expanded Parent Sections ({len(parent_sections)} fetched from Store) ---")
                for i, ps in enumerate(parent_sections, 1):
                    pid = ps.get("parent_id", "N/A")
                    title = ps.get("topic_title", "Untitled")
                    src = ps.get("source", "Unknown")
                    content = ps.get("content", ps.get("parent_text", "")).strip()
                    lines.append(f"\n[Parent #{i} | ID: {pid} | Title: '{title}' | Source: {src}]")
                    lines.append(content)

            web_results = rag.get("web_results", [])
            if web_results:
                lines.append(f"\n--- Grounding Web Search Results ({len(web_results)} found) ---")
                for i, wr in enumerate(web_results, 1):
                    lines.append(f"\n[Web Result #{i} | {wr.get('title', 'No Title')}] ({wr.get('url', '')})")
                    lines.append(wr.get("snippet", ""))

        # Context Sent to LLM
        generation = trace_data.get("generation", {})
        if generation:
            lines.append("\n" + _format_divider("4. PROMPT & CONTEXT PASSED TO GENERATION LLM", 60, "-"))
            lines.append(f"Model: {generation.get('model', 'N/A')}")
            messages = generation.get("messages", [])
            if messages:
                for msg in messages:
                    role = msg.get("role", "").upper()
                    content = msg.get("content", "")
                    lines.append(f"\n>>> [{role} MESSAGE] >>>")
                    lines.append(content)
            elif "context_sent" in generation:
                lines.append(f"\n>>> [CONTEXT SENT] >>>\n{generation.get('context_sent')}")

        # Final LLM output
        answer = trace_data.get("answer", trace_data.get("response", ""))
        lines.append("\n" + _format_divider("5. FINAL LLM RESPONSE", 60, "-"))
        lines.append(answer if answer else "(No answer generated)")
        lines.append(_format_divider("", 80, "=") + "\n")

        with open(HUMAN_LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as exc:
        print(f"[llm_logger] Failed to write to {HUMAN_LOG_FILE}: {exc}")


def print_terminal_context_transparency(
    query: str,
    similarity: float,
    legacy_index: bool,
    retrieved_chunks: list[dict],
    context_str: str,
) -> None:
    """
    Formatted terminal output for Path D similarity search and parent-child expansion.
    """
    print("\n" + "=" * 60)
    print("🔍 DEBUG: WHAT THE LLM IS SEEING (PATH D RETRIEVAL CONTEXT)")
    print("=" * 60)
    print(f"📌 User Query          : {query}")
    print(f"📊 Top Similarity Score: {similarity:.3f}")
    print(f"🏷️  Index Mode          : {'Legacy RAG' if legacy_index else 'Parent-Child RAG'}")

    print("\n--- 1. MATCHED CHILD CHUNK(S) (From ChromaDB) ---")
    if retrieved_chunks:
        for idx, ch in enumerate(retrieved_chunks[:2], 1):
            score_val = ch.get("similarity_score", ch.get("score", "N/A"))
            src_val = ch.get("source", "Unknown")
            pg_ts = ch.get("page_or_timestamp", "N/A")
            print(f"\n[Chunk #{idx} | Score: {score_val} | Source: {src_val} | Pos: {pg_ts}]")
            print(ch.get("chunk_text", "").strip())
    else:
        print("(No child chunks above similarity threshold)")

    print("\n--- 2. FULL PARENT SECTION(S) SENT TO LLM (From JSON Store) ---")
    if context_str.strip():
        print(context_str.strip())
    else:
        print("(No parent context assembled)")
    print("\n" + "=" * 60 + "\n")
