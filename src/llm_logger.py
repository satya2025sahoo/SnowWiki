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

Log organisation (session-wise + per-question):
  logs/
  ├── llm_context.log                   ← ALWAYS the latest query trace (overwritten each time)
  ├── llm_interactions.jsonl            ← Global audit log (append-only JSONL)
  └── sessions/
      └── <branch>/
          └── <session_id>/
              ├── session_trace.log     ← Full conversation trace for this session
              ├── interactions.jsonl    ← JSONL records for this session
              └── q01_<ts>_<slug>.log  ← One file per user question
"""

from __future__ import annotations

import datetime
import json
import os
import re
from typing import Any

from src.config import LOGS_DIR

# Root-level files (kept for IDE / developer convenience)
HUMAN_LOG_FILE = os.path.join(LOGS_DIR, "llm_context.log")
JSONL_LOG_FILE = os.path.join(LOGS_DIR, "llm_interactions.jsonl")

# Session-level sub-directory root
SESSIONS_DIR = os.path.join(LOGS_DIR, "sessions")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_divider(title: str = "", width: int = 70, char: str = "=") -> str:
    if not title:
        return char * width
    prefix = f"{char * 3} {title} "
    return prefix + char * max(0, width - len(prefix))


def _safe_dirname(name: str) -> str:
    """Convert a branch/session name into a filesystem-safe directory component."""
    name = str(name).strip()
    # Replace any character that isn't alphanumeric, dash, underscore, or dot
    name = re.sub(r"[^\w\-.]", "_", name)
    # Collapse multiple consecutive underscores/dashes
    name = re.sub(r"[_\-]{2,}", "_", name)
    return name[:80] or "default"


def _make_query_slug(query: str, max_words: int = 6) -> str:
    """Return a short, URL/filename-safe slug of the first few words of *query*."""
    words = re.sub(r"[^\w\s]", "", query.lower()).split()[:max_words]
    slug = "-".join(words)
    return slug[:50] or "query"


def _next_question_index(session_dir: str) -> int:
    """Count existing q*.log files in *session_dir* to determine the next question number."""
    try:
        existing = [
            f for f in os.listdir(session_dir)
            if re.match(r"^q\d+_.*\.log$", f)
        ]
        return len(existing) + 1
    except FileNotFoundError:
        return 1


def _build_trace_text(
    trace_data: dict[str, Any],
    timestamp: str,
    session_id: str,
    branch: str,
    query_idx: int,
    per_q_path: str | None = None,
) -> str:
    """Build the full human-readable text block for one query trace."""
    lines: list[str] = []

    # Header banner
    lines.append("\n" + _format_divider(f"QUERY TRACE [{timestamp}]", 80, "="))
    if per_q_path:
        lines.append(f"📁 Log File      : {per_q_path}")
    lines.append(f"🔑 Session ID    : {session_id}")
    lines.append(f"📌 User Query    : {trace_data.get('query', 'N/A')}")
    lines.append(f"🌿 Active Branch : {branch}")
    lines.append(f"🎯 Route / Stage : {trace_data.get('stage_used', trace_data.get('route', 'N/A'))}")

    # Intent classification block
    classifier = trace_data.get("classifier", {})
    if classifier:
        lines.append("\n" + _format_divider("1. INTENT CLASSIFICATION", 60, "-"))
        lines.append(f"Model       : {classifier.get('model', 'N/A')}")
        lines.append(
            f"Intent      : {classifier.get('intent', 'N/A')} "
            f"(rag_sub_intent: {classifier.get('rag_sub_intent', 'N/A')})"
        )
        lines.append(f"Confidence  : {classifier.get('confidence', 'N/A')}")
        if "raw_output" in classifier:
            lines.append(f"Raw Output  : {classifier.get('raw_output')}")

    # Memory Context
    memory = trace_data.get("memory", {})
    if memory:
        lines.append("\n" + _format_divider("2. CONVERSATION MEMORY CONTEXT", 60, "-"))
        summary = memory.get("running_summary", "").strip()
        recent  = memory.get("recent_turns_text", "").strip()
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
                src   = chunk.get("source", "Unknown")
                pos   = chunk.get("page_or_timestamp", "N/A")
                txt   = chunk.get("chunk_text", "").strip()
                lines.append(f"\n[Chunk #{i} | Score: {score} | Source: {src} | Pos: {pos}]")
                lines.append(txt)

        parent_sections = rag.get("parent_sections", [])
        if parent_sections:
            lines.append(f"\n--- Expanded Parent Sections ({len(parent_sections)} fetched from Store) ---")
            for i, ps in enumerate(parent_sections, 1):
                pid     = ps.get("parent_id", "N/A")
                title   = ps.get("topic_title", "Untitled")
                src     = ps.get("source", "Unknown")
                content = ps.get("content", ps.get("parent_text", "")).strip()
                lines.append(f"\n[Parent #{i} | ID: {pid} | Title: '{title}' | Source: {src}]")
                lines.append(content)

        web_results = rag.get("web_results", [])
        if web_results:
            lines.append(f"\n--- Grounding Web Search Results ({len(web_results)} found) ---")
            for i, wr in enumerate(web_results, 1):
                lines.append(
                    f"\n[Web Result #{i} | {wr.get('title', 'No Title')}] ({wr.get('url', '')})"
                )
                lines.append(wr.get("snippet", ""))

    # Context Sent to LLM
    generation = trace_data.get("generation", {})
    if generation:
        lines.append("\n" + _format_divider("4. PROMPT & CONTEXT PASSED TO GENERATION LLM", 60, "-"))
        lines.append(f"Model: {generation.get('model', 'N/A')}")
        messages = generation.get("messages", [])
        if messages:
            for msg in messages:
                role    = msg.get("role", "").upper()
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

    return "\n".join(lines)


# ── Main Public Function ────────────────────────────────────────────────────────

def log_llm_interaction(trace_data: dict[str, Any]) -> None:
    """
    Log an entire query lifecycle.

    Creates / appends to:
      1. logs/sessions/<branch>/<session_id>/q<N>_<ts>_<slug>.log  — per-question
      2. logs/sessions/<branch>/<session_id>/session_trace.log      — full session trace
      3. logs/sessions/<branch>/<session_id>/interactions.jsonl     — session JSONL
      4. logs/llm_context.log                                        — latest query (overwritten)
      5. logs/llm_interactions.jsonl                                 — global JSONL audit log
    """
    timestamp   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time_str    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    branch      = trace_data.get("branch", "default")
    session_id  = trace_data.get("session_id", "default_session")
    query_text  = trace_data.get("query", "")

    trace_data_with_ts = {"timestamp": timestamp, **trace_data}

    # ── Build session directory ────────────────────────────────────────────────
    safe_branch  = _safe_dirname(branch)
    safe_session = _safe_dirname(session_id)
    session_dir  = os.path.join(SESSIONS_DIR, safe_branch, safe_session)
    os.makedirs(session_dir, exist_ok=True)

    # Determine question index + slug
    query_idx  = _next_question_index(session_dir)
    slug       = _make_query_slug(query_text)
    per_q_name = f"q{query_idx:02d}_{time_str}_{slug}.log"
    per_q_path = os.path.join(session_dir, per_q_name)

    # Build text trace (shared by all text outputs)
    trace_text = _build_trace_text(
        trace_data  = trace_data,
        timestamp   = timestamp,
        session_id  = session_id,
        branch      = branch,
        query_idx   = query_idx,
        per_q_path  = per_q_path,
    )

    # ── 1. Write individual question log ──────────────────────────────────────
    try:
        with open(per_q_path, "w", encoding="utf-8") as f:
            f.write(trace_text)
    except Exception as exc:
        print(f"[llm_logger] Failed to write per-question log {per_q_path}: {exc}")

    # ── 2. Append to session trace ────────────────────────────────────────────
    session_trace_path = os.path.join(session_dir, "session_trace.log")
    try:
        with open(session_trace_path, "a", encoding="utf-8") as f:
            f.write(trace_text)
    except Exception as exc:
        print(f"[llm_logger] Failed to append to {session_trace_path}: {exc}")

    # ── 3. Append to session JSONL ────────────────────────────────────────────
    session_jsonl_path = os.path.join(session_dir, "interactions.jsonl")
    try:
        with open(session_jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_data_with_ts, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[llm_logger] Failed to append to {session_jsonl_path}: {exc}")

    # ── 4. Overwrite root llm_context.log with the LATEST query trace ─────────
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(HUMAN_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(trace_text)
    except Exception as exc:
        print(f"[llm_logger] Failed to write to {HUMAN_LOG_FILE}: {exc}")

    # ── 5. Append to global JSONL audit log ───────────────────────────────────
    try:
        with open(JSONL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_data_with_ts, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[llm_logger] Failed to write to {JSONL_LOG_FILE}: {exc}")


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
    try:
        def _safe_print(text: str = "") -> None:
            try:
                print(text)
            except UnicodeEncodeError:
                # Fallback for Windows consoles using legacy cp1252 encoding
                print(text.encode("ascii", errors="replace").decode("ascii"))

        _safe_print("\n" + "=" * 60)
        _safe_print("[DEBUG: WHAT THE LLM IS SEEING (PATH D RETRIEVAL CONTEXT)]")
        _safe_print("=" * 60)
        _safe_print(f"User Query          : {query}")
        _safe_print(f"Top Similarity Score: {similarity:.3f}")
        _safe_print(f"Index Mode          : {'Legacy RAG' if legacy_index else 'Parent-Child RAG'}")

        _safe_print("\n--- 1. MATCHED CHILD CHUNK(S) (From ChromaDB) ---")
        if retrieved_chunks:
            for idx, ch in enumerate(retrieved_chunks[:2], 1):
                score_val = ch.get("similarity_score", ch.get("score", "N/A"))
                src_val   = ch.get("source", "Unknown")
                pg_ts     = ch.get("page_or_timestamp", "N/A")
                _safe_print(f"\n[Chunk #{idx} | Score: {score_val} | Source: {src_val} | Pos: {pg_ts}]")
                _safe_print(ch.get("chunk_text", "").strip())
        else:
            _safe_print("(No child chunks above similarity threshold)")

        _safe_print("\n--- 2. FULL PARENT SECTION(S) SENT TO LLM (From JSON Store) ---")
        if context_str.strip():
            _safe_print(context_str.strip())
        else:
            _safe_print("(No parent context assembled)")
        _safe_print("\n" + "=" * 60 + "\n")
    except Exception as exc:
        print(f"[llm_logger] print_terminal_context_transparency suppressed error: {exc}")
