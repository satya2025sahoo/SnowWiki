"""
src/search_service.py
=====================
Google Custom Search API integration.

Used as a fallback when local ChromaDB RAG context is insufficient.
Targets ServiceNow documentation and general ServiceNow topics.
"""

from __future__ import annotations

from googleapiclient.discovery import build

from src.config import GOOGLE_API_KEY, GOOGLE_CSE_ID, GOOGLE_SEARCH_MAX_RESULTS


def google_search_servicenow(query: str, num_results: int = GOOGLE_SEARCH_MAX_RESULTS) -> list[dict]:
    """
    Query Google Custom Search API for ServiceNow-related results.

    Prepends 'ServiceNow' to the query so generic CSEs still surface
    on-topic results; if the CSE is already restricted to
    docs.servicenow.com the prefix is harmlessly redundant.

    Args:
        query:       The user's original question / search phrase.
        num_results: Max number of results to return (1–10, CSE limit).

    Returns:
        List of dicts with keys: title, url, snippet.
        Returns an empty list on any API error.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    # Ensure the query is scoped to ServiceNow topics
    scoped_query = f"ServiceNow {query}" if "servicenow" not in query.lower() else query

    try:
        service = build(
            "customsearch",
            "v1",
            developerKey=GOOGLE_API_KEY,
            cache_discovery=False,   # avoids file-based cache warnings in Streamlit
        )
        response = (
            service.cse()
            .list(
                q=scoped_query,
                cx=GOOGLE_CSE_ID,
                num=min(num_results, 10),   # CSE hard limit is 10
            )
            .execute()
        )

        results: list[dict] = []
        for item in response.get("items", []):
            results.append(
                {
                    "title":   item.get("title", "ServiceNow Docs"),
                    "url":     item.get("link", "https://docs.servicenow.com"),
                    "snippet": item.get("snippet", ""),
                }
            )
        return results

    except Exception as exc:
        # Log and degrade gracefully — the caller will handle empty results
        print(f"[search_service] Google Custom Search error: {exc}")
        return []


def format_search_results_for_prompt(results: list[dict]) -> str:
    """
    Format search result dicts into a compact string suitable for
    injection into an LLM prompt.
    """
    if not results:
        return "No web search results found."

    lines: list[str] = []
    for i, r in enumerate(results, start=1):
        lines.append(
            f"[Result {i}] {r['title']}\n"
            f"URL: {r['url']}\n"
            f"Excerpt: {r['snippet']}"
        )
    return "\n\n".join(lines)
