# SnowWiki Smart Routing AI

SnowWiki is a Streamlit-driven ServiceNow knowledge assistant with a modular, industry-standard dual-backend architecture. It supports **Groq cloud inference** and **self-hosted local LLMs** (via an OpenAI-compatible FastAPI server), orchestrated with **LangChain**, **LangGraph**, and **LangSmith**.

---

## Architecture

```
User Query
    │
    ▼
[LangGraph] classify_intent (small model)
    │
    ├──► GREETING     → Small LLM response
    ├──► OUT_OF_SCOPE → Static polite rejection
    └──► SERVICENOW   → ChromaDB RAG → Large LLM
                            └── (insufficient?) → Google Search → Large LLM
```

| Component | Groq Mode | Local LLM Mode |
|---|---|---|
| Intent classifier | `llama-3.1-8b-instant` | `SMALL_MODEL_NAME` |
| RAG / response | `llama-3.1-8b-instant` | `LARGE_MODEL_NAME` |
| Server | Groq Cloud | `local_llm_server.py` (FastAPI) |
| Auth | `GROQ_API_KEY` | None (or `LOCAL_LLM_API_KEY`) |

---

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `.env`

Create a `.env` file in the project root:

```env
# ── LLM Backend Toggle ──────────────────────────────────────────────────────
# Set to true to use local FastAPI server; false for Groq cloud (default)
USE_LOCAL_LLM=false

# ── Groq Cloud (used when USE_LOCAL_LLM=false) ─────────────────────────────
GROQ_API_KEY=your_groq_api_key_here

# ── Local LLM Server (used when USE_LOCAL_LLM=true) ────────────────────────
LOCAL_LLM_ENDPOINT=https://127.0.0.1:8000
LOCAL_LLM_API_KEY=                        # Leave blank if no auth required

# ── Model Name Overrides (local mode only) ──────────────────────────────────
SMALL_MODEL_NAME=test-model               # Maps to your local model for classification
LARGE_MODEL_NAME=test-model               # Maps to your local model for RAG answers

# ── Google Custom Search (optional web fallback) ────────────────────────────
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_custom_search_engine_id_here

# ── LangSmith Observability (optional) ─────────────────────────────────────
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=snowwiki
```

---

## Running the Local LLM Backend (FastAPI)

The `local_llm_server.py` implements an OpenAI-compatible `/v1/chat/completions` endpoint. By default it echoes the prompt — replace `_call_underlying_llm()` with a real model call for production.

### Generate a Self-Signed SSL Certificate (once)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout server.key -out server.crt \
  -subj "/CN=localhost"
```

> **Note:** The client automatically sets `verify=False` to support self-signed certificates, so no CA trust configuration is needed.

### Start the FastAPI Server

```bash
# HTTP (development / testing)
uvicorn local_llm_server:app --host 0.0.0.0 --port 8000

# HTTPS with self-signed cert
uvicorn local_llm_server:app --host 0.0.0.0 --port 8443 \
  --ssl-keyfile server.key --ssl-certfile server.crt
```

### Test the Endpoint

```bash
curl -k -X POST https://127.0.0.1:8443/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"test-model","messages":[{"role":"user","content":"Hello"}]}'
```

---

## Switching Backends

| `.env` setting | Behavior |
|---|---|
| `USE_LOCAL_LLM=false` | Routes inference to Groq — requires `GROQ_API_KEY` |
| `USE_LOCAL_LLM=true` | Routes inference to `LOCAL_LLM_ENDPOINT` — no Groq key needed |

---

## Running the Application

```bash
streamlit run app.py
```

---

## Testing

All unit tests mock HTTP calls and require no live API keys or running servers.

```bash
# Via venv (Windows)
.venv\Scripts\python.exe -m pytest -v

# If pytest is on your PATH
pytest -v
```

**Test coverage:**

| Test File | What it covers |
|---|---|
| `tests/test_factory.py` | `get_llm()` returns correct wrapper class; model name selection |
| `tests/test_local_llm.py` | `LocalLLM` URL targeting, OpenAI response parsing, SSL `verify=False` |

---

## LangSmith Tracing

If `LANGSMITH_API_KEY` is set in `.env`, `init_tracing()` automatically enables LangChain distributed tracing. All LangGraph node executions and LLM calls will appear in your [LangSmith dashboard](https://smith.langchain.com) under the `LANGSMITH_PROJECT` name.

No code changes are needed — tracing is fully opt-in via the env var.

---

## File Structure

```
SnowWiki/
├── app.py                    # Streamlit frontend
├── local_llm_server.py       # FastAPI OpenAI-compatible local LLM server
├── requirements.txt
├── .env                      # Secrets (not committed)
├── src/
│   ├── config.py             # Centralized env var loading
│   ├── llm_wrapper.py        # GroqLLM, LocalLLM, get_llm() factory
│   ├── chains.py             # LangChain prompt templates & chain builders
│   ├── graph.py              # LangGraph state graph (intent → route → answer)
│   ├── tracing.py            # LangSmith init
│   ├── retriever.py          # ChromaDB RAG + Google Search fallback
│   ├── memory.py             # Conversation memory manager
│   ├── ingestion.py          # Document & media ingestion → ChromaDB
│   ├── transcriber.py        # Groq Whisper STT & summarization
│   └── servicenow_domain.py  # ServiceNow domain classifier prompt
└── tests/
    ├── test_factory.py       # LLM factory unit tests
    └── test_local_llm.py     # LocalLLM wrapper unit tests
```
