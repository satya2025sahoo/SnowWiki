"""
src/config.py
=============
Centralized configuration loader for SnowWiki Smart Routing Agent.
Loads secrets from .env (GROQ_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID)
and defines all directory paths and model constants.
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

# Ensure all required directories exist on import
for _path in [CHROMA_DB_DIR, DATA_DIR, TRANSCRIPTS_DIR,
              PROJECT_STATES_DIR, UPLOADS_DIR, CHAT_HISTORY_DIR]:
    os.makedirs(_path, exist_ok=True)

# ── API Keys (read-only from environment) ─────────────────────────────────────
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID  = os.environ.get("GOOGLE_CSE_ID", "")

# ── Groq Model Constants ───────────────────────────────────────────────────────
# Fast small model — intent classification & greeting responses & memory compaction
GROQ_CLASSIFIER_MODEL = "llama-3.1-8b-instant"

# High-capability model — RAG answer generation & web-grounded responses
GROQ_RESPONSE_MODEL   = "llama-3.1-8b-instant"

# ── ChromaDB / Embedding ───────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME      = "snow_wiki_knowledge"
SIMILARITY_THRESHOLD = 0.45   # cosine similarity floor for local RAG hit

# ── Routing Constants ──────────────────────────────────────────────────────────
# Sentinel string the 70B model emits when local context is insufficient
INSUFFICIENT_CONTEXT_MARKER = "INSUFFICIENT_CONTEXT"

# Google Custom Search — max results per fallback call
GOOGLE_SEARCH_MAX_RESULTS = 5
