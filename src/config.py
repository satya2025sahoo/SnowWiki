"""
src/config.py
=============
Centralalized configuration loader for SnowWiki Smart Routing Agent.
Loads secrets from .env and defines all directory paths and model constants.

Backend toggle:
  USE_LOCAL_LLM=true  → route all inference through the local FastAPI server.
  USE_LOCAL_LLM=false → route through Groq cloud (default).
"""

import os
from dotenv import load_dotenv

# Load secrets from .env at import time
load_dotenv()

# ── Directory Paths ────────────────────────────────────────────────────────────
BASE_DIR            = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHROMA_DB_DIR       = os.path.join(BASE_DIR, "chroma_db")
DATA_DIR            = os.path.join(BASE_DIR, "data")
TRANSCRIPTS_DIR     = os.path.join(DATA_DIR, "transcripts")
PROJECT_STATES_DIR  = os.path.join(DATA_DIR, "project_states")
UPLOADS_DIR         = os.path.join(DATA_DIR, "uploads")
CHAT_HISTORY_DIR    = os.path.join(DATA_DIR, "chat_history")
SESSIONS_DIR        = CHAT_HISTORY_DIR
PARENT_STORE_DIR    = os.path.join(DATA_DIR, "parent_store")   # Semantic Parent-Child RAG

# Ensure all required directories exist on import
for _path in [CHROMA_DB_DIR, DATA_DIR, TRANSCRIPTS_DIR,
              PROJECT_STATES_DIR, UPLOADS_DIR, CHAT_HISTORY_DIR, SESSIONS_DIR,
              PARENT_STORE_DIR]:
    os.makedirs(_path, exist_ok=True)

# ── API Keys (read-only from environment) ─────────────────────────────────────
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID  = os.environ.get("GOOGLE_CSE_ID", "")

# ── Dual-Backend Toggle ────────────────────────────────────────────────────────
# Set USE_LOCAL_LLM=true in .env to route inference to the local FastAPI server.
USE_LOCAL_LLM: bool = os.environ.get("USE_LOCAL_LLM", "false").strip().lower() in ("1", "true", "yes")

# Local FastAPI server endpoint (supports self-signed SSL; SSL verify is disabled client-side)
LOCAL_LLM_ENDPOINT: str = os.environ.get("LOCAL_LLM_ENDPOINT", "https://127.0.0.1:8000")

# Optional bearer token for the local server (leave blank if no auth required)
LOCAL_LLM_API_KEY: str = os.environ.get("LOCAL_LLM_API_KEY", "")

# ── Model Name Overrides ───────────────────────────────────────────────────────
# Used when USE_LOCAL_LLM=true — map to whatever models your local server serves.
# Default to "test-model" so the echo stub works out of the box.
SMALL_MODEL_NAME: str = os.environ.get("SMALL_MODEL_NAME", "test-model")
LARGE_MODEL_NAME: str = os.environ.get("LARGE_MODEL_NAME", "test-model")

# ── LangSmith Observability ────────────────────────────────────────────────────
LANGSMITH_API_KEY: str = os.environ.get("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT: str = os.environ.get("LANGSMITH_PROJECT", "snowwiki")

# ── Groq Model Constants ───────────────────────────────────────────────────────
# Fast small model — intent classification & greeting responses & memory compaction
GROQ_CLASSIFIER_MODEL = "groq/compound-mini"

# High-capability model — RAG answer generation & web-grounded responses
GROQ_RESPONSE_MODEL   = "openai/gpt-oss-20b"

# Whisper STT model
GROQ_WHISPER_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3")

# ── ChromaDB / Embedding ───────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME      = "snow_wiki_knowledge"
SIMILARITY_THRESHOLD = 0.45   # cosine similarity floor for local RAG hit

# ── Routing Constants ──────────────────────────────────────────────────────────
# Sentinel string the 70B model emits when local context is insufficient
INSUFFICIENT_CONTEXT_MARKER = "INSUFFICIENT_CONTEXT"

# Google Custom Search — max results per fallback call
GOOGLE_SEARCH_MAX_RESULTS = 5
