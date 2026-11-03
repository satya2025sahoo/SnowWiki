"""
src/route_handlers/web_fallback.py
==================================
Path D fallback handler: Google Custom Search when local RAG context is insufficient.
"""
from __future__ import annotations

from src.config import GROQ_RESPONSE_MODEL
from src.search_service import google_search_servicenow, format_search_results_for_prompt
from src.answer_generators import generate_web_answer


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
    status = search_response.get("status", "ERROR")
    error_msg = search_response.get("error_message", "")
    web_results = search_response.get("results", [])

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
