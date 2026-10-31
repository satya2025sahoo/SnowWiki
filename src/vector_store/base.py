"""
src/vector_store/base.py
========================
Abstract VectorStore interface — repository pattern that decouples the
rest of the application from any specific vector database implementation.

Implementations:
    ChromaVectorStore  (src/vector_store/chroma_store.py)  — legacy, embedded SQLite
    QdrantVectorStore  (src/vector_store/qdrant_store.py)  — production, embedded or gRPC

The active backend is controlled by the VECTOR_STORE_BACKEND env var (default: "qdrant").
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseVectorStore(ABC):
    """
    Common contract for all vector database backends.

    Every method accepts a ``branch`` name so a single store instance
    can serve multi-tenant branches without repeated initialisation.
    """

    # ── Write Operations ────────────────────────────────────────────────────────

    @abstractmethod
    def upsert_chunks(
        self,
        branch: str,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """
        Insert or update chunks in the store.

        Args:
            branch:     Branch / tenant name (used as collection / namespace key).
            ids:        Stable string IDs for each chunk.
            documents:  Embed texts (preamble + body) sent to the search index.
            embeddings: Pre-computed dense float vectors (one per document).
            metadatas:  Flat string/int/float metadata dict for each chunk.
        """

    @abstractmethod
    def delete_file(self, branch: str, filename: str) -> int:
        """
        Remove all chunks whose ``source_file`` metadata equals *filename*
        from the given branch.

        Returns:
            Number of chunks deleted.
        """

    # ── Read Operations ─────────────────────────────────────────────────────────

    @abstractmethod
    def query(
        self,
        branch: str,
        query_embedding: List[float],
        top_k: int = 20,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Dense vector similarity search.

        Returns a dict with keys ``ids``, ``documents``, ``metadatas``,
        ``distances`` — same shape as ChromaDB's ``collection.query()``
        result for drop-in compatibility.
        """

    @abstractmethod
    def get_all(
        self,
        branch: str,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Return all stored chunks for the branch.

        Args:
            include: Subset of ["documents", "metadatas", "embeddings"].
        """

    # ── Utility ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def collection_exists(self, branch: str) -> bool:
        """Return True if the branch collection / namespace exists."""

    @abstractmethod
    def count(self, branch: str) -> int:
        """Return the total number of chunks stored for this branch."""

    def close(self) -> None:
        """Release any database connections or locks."""
        pass
