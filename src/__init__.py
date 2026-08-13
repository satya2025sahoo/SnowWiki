"""
SnowWiki Smart Routing AI Agent — Core Package

Modules:
  config         — Path constants, Groq model names, env variable loading
  search_service — Google Custom Search API fallback integration
  transcriber    — Groq Whisper STT, file summaries, branch state management
  ingestion      — ChromaDB vector indexing, document chunking, ingestion pipeline
  retriever      — 3-stage smart routing: intent classify → RAG / web fallback
  memory         — Persistent JSON chat history, sliding window, memory compaction
"""
