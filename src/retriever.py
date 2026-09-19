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

This file is the public entry point only.  Implementation is split across:
  src/intent_classifier.py   — Stage 1 classification
  src/route_handlers.py      — Path A–E handlers + retrieval helpers
  src/answer_generators.py   — LLM answer-generation helpers
"""

from __future__ import annotations

from src.config import GROQ_CLASSIFIER_MODEL
from src.intent_classifier import classify_intent
from src.route_handlers import (
    _handle_greeting,
    _handle_conversational,
    _handle_out_of_scope,
    _handle_servicenow,
)
from src.llm_logger import log_llm_interaction


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
            "query":      query_text,
            "branch":     active_branch,
            "stage_used": result.get("stage_used", ""),
            "route":      result.get("route", ""),
            "classifier": classifier_trace,
            "memory":     memory_context or {},
            "rag":        handler_trace.get("rag_details", {}),
            "generation": handler_trace.get("generation_details", {}),
            "answer":     result.get("answer", result.get("response", "")),
        })
    except Exception as log_exc:
        print(f"[retriever] Logger error: {log_exc}")

    return result
