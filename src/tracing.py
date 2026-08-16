"""
src/tracing.py
==============
LangSmith observability initializer.

Call `init_tracing()` once at application startup.
If LANGSMITH_API_KEY is not set, tracing is silently skipped.

Environment variables read:
  LANGSMITH_API_KEY  — your LangSmith API key (required to enable tracing)
  LANGSMITH_PROJECT  — project name shown in the LangSmith UI (default: "snowwiki")
"""

import os
from .config import LANGSMITH_API_KEY, LANGSMITH_PROJECT


def init_tracing() -> None:
    """
    Initialize LangSmith tracing by setting the required environment variables.

    LangChain / LangGraph automatically pick up LANGCHAIN_* env vars at runtime,
    so we set them here rather than passing them to a Client constructor.
    """
    if not LANGSMITH_API_KEY:
        return  # Tracing disabled — no key configured

    os.environ.setdefault("LANGCHAIN_TRACING_V2",  "true")
    os.environ.setdefault("LANGCHAIN_API_KEY",      LANGSMITH_API_KEY)
    os.environ.setdefault("LANGCHAIN_PROJECT",      LANGSMITH_PROJECT)
    os.environ.setdefault("LANGCHAIN_ENDPOINT",     "https://api.smith.langchain.com")
