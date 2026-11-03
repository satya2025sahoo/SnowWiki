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
LOGS_DIR            = os.path.join(BASE_DIR, "logs")

# Ensure all required directories exist on import
for _path in [CHROMA_DB_DIR, DATA_DIR, TRANSCRIPTS_DIR,
              PROJECT_STATES_DIR, UPLOADS_DIR, CHAT_HISTORY_DIR, SESSIONS_DIR,
              PARENT_STORE_DIR, LOGS_DIR]:
    os.makedirs(_path, exist_ok=True)

# ── API Keys (read-only from environment) ─────────────────────────────────────
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID  = os.environ.get("GOOGLE_CSE_ID", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
# Qwen-2.5-VL-72B-Instruct is the primary vision model (flowcharts, tables, diagrams, OCR)
OPENROUTER_VISION_MODEL = os.environ.get("OPENROUTER_VISION_MODEL", "qwen/qwen2.5-vl-72b-instruct")
# Set VISION_LLM_PROVIDER=local to use a local vision model (e.g. Ollama + Qwen3-VL / Qwen2.5-VL)
_raw_vision_p = os.environ.get("VISION_LLM_PROVIDER", "").strip().lower()
VISION_LLM_PROVIDER = _raw_vision_p if _raw_vision_p in ("local", "openrouter", "groq") else "local"
LOCAL_VISION_ENDPOINT = os.environ.get("LOCAL_VISION_ENDPOINT", "http://127.0.0.1:11434/v1")
_raw_vision_m = os.environ.get("LOCAL_VISION_MODEL", "").strip()
LOCAL_VISION_MODEL = _raw_vision_m if _raw_vision_m and _raw_vision_m != "llava" else "qwen3-vl:8b"

# ── Dual-Backend Toggle ────────────────────────────────────────────────────────
# Set USE_LOCAL_LLM=true in .env to route inference to the local Ollama server.
USE_LOCAL_LLM: bool = os.environ.get("USE_LOCAL_LLM", "true").strip().lower() in ("1", "true", "yes")

# Local Ollama endpoint (default: http://127.0.0.1:11434)
LOCAL_LLM_ENDPOINT: str = os.environ.get("LOCAL_LLM_ENDPOINT", "http://127.0.0.1:11434")

# Optional bearer token for the local server (leave blank if no auth required)
LOCAL_LLM_API_KEY: str = os.environ.get("LOCAL_LLM_API_KEY", "")

# ── Model Name Overrides (6-7 GB VRAM Local Profile) ───────────────────────────
_raw_small = os.environ.get("SMALL_MODEL_NAME", "").strip()
SMALL_MODEL_NAME: str = _raw_small if _raw_small and _raw_small not in ("test-model", "llama3.1") else "qwen3:0.6b"

_raw_large = os.environ.get("LARGE_MODEL_NAME", "").strip()
LARGE_MODEL_NAME: str = _raw_large if _raw_large and _raw_large not in ("test-model", "llama3.1") else "qwen3:8b"

# Classifier backend: "jev" / "discriminative" (open-source local NLI) or "llm" (Ollama / Groq)
CLASSIFIER_BACKEND: str = os.environ.get("CLASSIFIER_BACKEND", "jev").strip().lower()

# ── LangSmith Observability ────────────────────────────────────────────────────
LANGSMITH_API_KEY: str = os.environ.get("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT: str = os.environ.get("LANGSMITH_PROJECT", "snowwiki")

# ── Groq Model Constants ───────────────────────────────────────────────────────
# Fast small model — intent classification & greeting responses & memory compaction
GROQ_CLASSIFIER_MODEL = "qwen/qwen3.8-27b"

# High-capability model — RAG answer generation & web-grounded responses
GROQ_RESPONSE_MODEL   = "openai/gpt-oss-20b"

# Whisper STT model
GROQ_WHISPER_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3")

# ── ChromaDB / Embedding ───────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME      = "snow_wiki_knowledge"
SIMILARITY_THRESHOLD = 0.45   # cosine similarity floor for local RAG hit

# ── Cross-Encoder Reranker ─────────────────────────────────────────────────────
RERANKER_MODEL_NAME        = os.environ.get("RERANKER_MODEL_NAME", "BAAI/bge-reranker-base")
RERANK_SCORE_THRESHOLD     = float(os.environ.get("RERANK_SCORE_THRESHOLD", "0.25"))
RERANK_TOP_N               = int(os.environ.get("RERANK_TOP_N", "5"))
RERANK_CANDIDATE_POOL_SIZE = int(os.environ.get("RERANK_CANDIDATE_POOL_SIZE", "20"))

# ── VectorStore Backend ────────────────────────────────────────────────────────
# "qdrant"  (default) → Qdrant embedded local (data/qdrant_storage/) — no Docker needed.
# "chroma"            → ChromaDB legacy SQLite (data/chroma_db/).
# Switch to Qdrant gRPC mode by also setting QDRANT_MODE=grpc in .env.
VECTOR_STORE_BACKEND = os.environ.get("VECTOR_STORE_BACKEND", "qdrant")

# Qdrant connection (only relevant when QDRANT_MODE=grpc)
QDRANT_MODE       = os.environ.get("QDRANT_MODE", "embedded")   # "embedded" | "grpc"
QDRANT_HOST       = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_GRPC_PORT  = int(os.environ.get("QDRANT_GRPC_PORT", "6334"))
QDRANT_REST_PORT  = int(os.environ.get("QDRANT_REST_PORT", "6333"))

# Dense embedding dimension — must match EMBEDDING_MODEL_NAME output dim
# all-MiniLM-L6-v2  → 384  (default)
# bge-small-en-v1.5 → 384
# all-mpnet-base-v2 → 768  (set EMBEDDING_DIM=768 in .env if switching)
EMBEDDING_DIM     = int(os.environ.get("EMBEDDING_DIM", "384"))

QDRANT_STORAGE_DIR = os.path.join(DATA_DIR, "qdrant_storage")
os.makedirs(QDRANT_STORAGE_DIR, exist_ok=True)

# ── Ingestion Idempotency ──────────────────────────────────────────────────────
# SHA-256 hex digest stored per file in branch state to detect unchanged files.
# On re-upload of the same bytes the pipeline skips all processing stages.
# On re-upload with changed bytes the pipeline deletes old ChromaDB chunks first.
CONTENT_HASH_FIELD = "content_sha256"

# ── Contextual Chunk Preamble ──────────────────────────────────────────────────
# Prepend a short breadcrumb header to every child chunk before embedding so
# the BM25 and dense models both see document / section context without
# polluting the visible answer text.
PREAMBLE_TEMPLATE = "[Document: {source_file} | Section: {section} | Branch: {branch}]\n"

# ── Routing Constants ──────────────────────────────────────────────────────────
# Sentinel string the 70B model emits when local context is insufficient
INSUFFICIENT_CONTEXT_MARKER = "INSUFFICIENT_CONTEXT"

# Google Custom Search — max results per fallback call
GOOGLE_SEARCH_MAX_RESULTS = 5
