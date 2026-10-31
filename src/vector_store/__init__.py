"""
src/vector_store/__init__.py
=============================
Public factory for the active VectorStore backend.

Usage::

    from src.vector_store import get_vector_store

    store = get_vector_store()
    store.upsert_chunks(branch, ids, docs, embeddings, metadatas)

Backend is selected by VECTOR_STORE_BACKEND in .env:
    "qdrant"  (default) → QdrantVectorStore (embedded local or gRPC)
    "chroma"            → ChromaVectorStore (legacy SQLite-backed)
"""

from __future__ import annotations

import os
import logging
from functools import lru_cache

from src.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)

_BACKEND_KEY = "VECTOR_STORE_BACKEND"


@lru_cache(maxsize=1)
def get_vector_store() -> BaseVectorStore:
    """
    Return the singleton VectorStore instance for the configured backend.

    The instance is cached after first call — safe to call repeatedly.
    """
    backend = os.environ.get(_BACKEND_KEY, "qdrant").strip().lower()

    if backend == "chroma":
        from src.vector_store.chroma_store import ChromaVectorStore
        logger.info("VectorStore backend: ChromaDB (legacy)")
        return ChromaVectorStore()

    # Default: Qdrant
    from src.vector_store.qdrant_store import QdrantVectorStore
    mode = os.environ.get("QDRANT_MODE", "embedded")
    logger.info("VectorStore backend: Qdrant (%s mode)", mode)
    return QdrantVectorStore()


__all__ = ["BaseVectorStore", "get_vector_store"]
