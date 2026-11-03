"""
src/graph.py
============
LangGraph state graph for SnowWiki Smart Routing.

Graph structure:
  START → classify_intent → (greeting | out_of_scope | servicenow) → END

SnowWikiState tracks the full query lifecycle: intent, routing branch,
memory context, answer, retrieved chunks, and grounding sources.
"""

from typing import TypedDict, Any, Optional, List
from langgraph.graph import StateGraph, START, END
from .chains import intent_classification_chain
from .retriever import _handle_servicenow, _handle_greeting, _handle_out_of_scope
from .servicenow_domain import get_classifier_domain_prompt
import json


# ── State Schema ───────────────────────────────────────────────────────────────

class SnowWikiState(TypedDict, total=False):
    query:              str
    branch:             str
    memory:             Optional[dict]
    intent:             Optional[str]
    confidence:         Optional[float]
    answer:             Optional[str]
    retrieved_chunks:   Optional[List[dict]]
    grounding_sources:  Optional[List[dict]]
    source_type:        Optional[str]
    badge:              Optional[str]
    badge_class:        Optional[str]
    route:              Optional[str]


# ── Node: Intent Classification ────────────────────────────────────────────────

def classify_intent(state: SnowWikiState) -> SnowWikiState:
    """Run the small LLM to classify the user query as GREETING/SERVICENOW/OUT_OF_SCOPE."""
    chain = intent_classification_chain()
    domain_prompt = get_classifier_domain_prompt()
    json_str = chain.run(domain_prompt=domain_prompt, query=state["query"])
    try:
        # Strip markdown code fences if the model wraps anyway
        import re
        json_str = re.sub(r"```(?:json)?|```", "", json_str).strip()
        data = json.loads(json_str)
        state["intent"]     = str(data.get("intent", "SERVICENOW")).upper()
        state["confidence"] = float(data.get("confidence", 0.5))
    except Exception:
        state["intent"]     = "SERVICENOW"
        state["confidence"] = 0.5
    return state


# ── Conditional Edge: Route ────────────────────────────────────────────────────

def route(state: SnowWikiState) -> str:
    """Map intent to the graph node name."""
    i = state.get("intent", "SERVICENOW")
    if i == "GREETING":
        return "greeting"
    if i == "OUT_OF_SCOPE":
        return "out_of_scope"
    return "servicenow"


# ── Node: Greeting ─────────────────────────────────────────────────────────────

def handle_greeting(state: SnowWikiState) -> SnowWikiState:
    result = _handle_greeting(state["query"], state.get("memory"))
    state.update(result)
    return state


# ── Node: Out of Scope ─────────────────────────────────────────────────────────

def handle_out_of_scope(state: SnowWikiState) -> SnowWikiState:
    result = _handle_out_of_scope(state["query"])
    state.update(result)
    return state


# ── Node: ServiceNow RAG ───────────────────────────────────────────────────────

def handle_servicenow(state: SnowWikiState) -> SnowWikiState:
    result = _handle_servicenow(state["query"], state["branch"], state.get("memory"))
    state.update(result)
    return state


# ── Graph Assembly ─────────────────────────────────────────────────────────────

graph = StateGraph(SnowWikiState)

graph.add_node("classify_intent", classify_intent)
graph.add_node("greeting",        handle_greeting)
graph.add_node("out_of_scope",    handle_out_of_scope)
graph.add_node("servicenow",      handle_servicenow)

# Use the START constant (not the string "START") for the entry edge
graph.add_edge(START, "classify_intent")
graph.add_conditional_edges(
    "classify_intent",
    route,
    {
        "greeting":    "greeting",
        "out_of_scope": "out_of_scope",
        "servicenow":  "servicenow",
    }
)
graph.add_edge("greeting",    END)
graph.add_edge("out_of_scope", END)
graph.add_edge("servicenow",  END)

# Compiled runnable — invoke with SnowWikiState dict
snowwiki_app = graph.compile()
