"""
src/route_handlers/__init__.py
==============================
Modular route handlers package for SnowWiki's Smart Routing pipeline.
Exposes all path handlers and helpers for full backwards compatibility.
"""
from __future__ import annotations

from src.route_handlers.conversation import (
    _search_summaries,
    _handle_greeting,
    _handle_conversational,
    _handle_out_of_scope,
)
from src.route_handlers.global_summary import _handle_global_summary
from src.route_handlers.image_manifest import resolve_image_manifest
from src.route_handlers.context_builder import (
    collapse_loops,
    _fetch_parent_child_context,
    _fetch_legacy_context,
)
from src.route_handlers.web_fallback import _handle_web_fallback
from src.route_handlers.detailed_fact import (
    _handle_detailed_fact,
    _handle_servicenow,
)

__all__ = [
    "_search_summaries",
    "_handle_greeting",
    "_handle_conversational",
    "_handle_out_of_scope",
    "_handle_global_summary",
    "resolve_image_manifest",
    "collapse_loops",
    "_fetch_parent_child_context",
    "_fetch_legacy_context",
    "_handle_web_fallback",
    "_handle_detailed_fact",
    "_handle_servicenow",
]
