"""
src/vector_store/chroma_store.py
=================================
ChromaDB implementation of BaseVectorStore — kept as the legacy fallback
and the source backend for the one-shot migration to Qdrant.

Uses the existing persistent ChromaDB client configured in src/ingestion/core.py.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class ChromaVectorStore(BaseVectorStore):
    """
    Thin wrapper around the existing ChromaDB persistent collection.

    All reads and writes go to the single shared ``snow_wiki_knowledge``
    collection (branch isolation is enforced via metadata filtering).
    """

    def __init__(self) -> None:
        from src.ingestion.core import get_chroma_collection
        self._collection = get_chroma_collection()

    # ── Write Operations ────────────────────────────────────────────────────────

    def upsert_chunks(
        self,
        branch: str,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        if not ids:
            return
        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.debug("ChromaDB: upserted %d chunks for branch '%s'", len(ids), branch)

    def delete_file(self, branch: str, filename: str) -> int:
        try:
            results = self._collection.get(
                where={
                    "$and": [
                        {"branch": {"$eq": branch}},
                        {"source_file": {"$eq": filename}},
                    ]
                },
                include=[],
            )
            ids = results.get("ids", [])
            if ids:
                self._collection.delete(ids=ids)
                logger.info(
                    "ChromaDB: deleted %d chunks for file '%s' in branch '%s'",
                    len(ids), filename, branch,
                )
            return len(ids)
        except Exception as exc:
            logger.warning("ChromaDB delete_file error: %s", exc)
            return 0

    # ── Read Operations ─────────────────────────────────────────────────────────

    def query(
        self,
        branch: str,
        query_embedding: List[float],
        top_k: int = 20,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        filter_clause = where or {"branch": {"$eq": branch}}
        return self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_clause,
            include=["documents", "metadatas", "distances"],
        )

    def get_all(
        self,
        branch: str,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        inc = include or ["documents", "metadatas"]
        return self._collection.get(
            where={"branch": {"$eq": branch}},
            include=inc,
        )

    # ── Utility ─────────────────────────────────────────────────────────────────

    def collection_exists(self, branch: str) -> bool:
        try:
            result = self._collection.get(
                where={"branch": {"$eq": branch}},
                limit=1,
                include=[],
            )
            return bool(result.get("ids"))
        except Exception:
            return False

    def count(self, branch: str) -> int:
        try:
            result = self._collection.get(
                where={"branch": {"$eq": branch}},
                include=[],
            )
            return len(result.get("ids", []))
        except Exception:
            return 0
