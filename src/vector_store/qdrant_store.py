"""
src/vector_store/qdrant_store.py
=================================
Qdrant implementation of BaseVectorStore.

Supports two connection modes controlled by QDRANT_MODE in .env:

  embedded  (default)  — stores data at data/qdrant_storage/ on disk.
                         No Docker, no network. Drop-in replacement for ChromaDB.
  grpc                 — connects to a running Qdrant server (Docker / K8s).
                         Configure QDRANT_HOST and QDRANT_PORT in .env.

Collection naming:
    Each branch is mapped to a Qdrant collection named:
        ``snowwiki_<safe_branch_name>``

Vector config:
    Dense vectors: cosine similarity, dimension from EMBEDDING_DIM (default 384
    for all-MiniLM-L6-v2; set 768 if you switch to bge-small-en-v1.5).

Payload filters mirror ChromaDB metadata, enabling per-branch and per-file
deletion using Qdrant's native payload index (no full collection scan).
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from src.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)

# ── Config helpers ─────────────────────────────────────────────────────────────

def _qdrant_storage_path() -> str:
    from src.config import DATA_DIR
    path = os.path.join(DATA_DIR, "qdrant_storage")
    os.makedirs(path, exist_ok=True)
    return path


def _safe_collection_name(branch: str) -> str:
    """Map a branch name to a valid Qdrant collection identifier."""
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", branch).strip("_")
    return f"snowwiki_{safe}"[:64]  # Qdrant max collection name length = 64


def _embedding_dim() -> int:
    return int(os.environ.get("EMBEDDING_DIM", "384"))


# ── Client singleton ───────────────────────────────────────────────────────────

_CLIENT = None


def _get_client():
    """Return (and lazily create) the Qdrant client singleton."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    from qdrant_client import QdrantClient

    mode = os.environ.get("QDRANT_MODE", "embedded").strip().lower()

    if mode == "grpc":
        host = os.environ.get("QDRANT_HOST", "localhost")
        port = int(os.environ.get("QDRANT_GRPC_PORT", "6334"))
        _CLIENT = QdrantClient(host=host, grpc_port=port, prefer_grpc=True)
        logger.info("Qdrant client: gRPC mode → %s:%d", host, port)
    else:
        storage = _qdrant_storage_path()
        _CLIENT = QdrantClient(path=storage)
        logger.info("Qdrant client: embedded mode → %s", storage)

    return _CLIENT


# ── QdrantVectorStore ──────────────────────────────────────────────────────────

class QdrantVectorStore(BaseVectorStore):
    """
    Production-grade vector store backed by Qdrant.

    Branch isolation is achieved via separate Qdrant collections, which
    enables per-branch deletion, filtering, and concurrent writes without
    the SQLite lock contention that ChromaDB suffers from.
    """

    BATCH_SIZE = 250  # Points per upsert batch — safe for 8 GB VRAM systems

    def __init__(self) -> None:
        self._client = _get_client()
        self._dim = _embedding_dim()
        self._ensure_payload_indexes_cache: set[str] = set()

    # ── Internal helpers ────────────────────────────────────────────────────────

    def _ensure_collection(self, collection_name: str) -> None:
        """Create the collection if it doesn't exist yet."""
        from qdrant_client.models import Distance, VectorParams

        existing = {c.name for c in self._client.get_collections().collections}
        if collection_name in existing:
            return

        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=self._dim,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Qdrant: created collection '%s' (dim=%d, cosine)", collection_name, self._dim)

    def _ensure_payload_indexes(self, collection_name: str) -> None:
        """Create keyword payload indexes for fast metadata filtering."""
        if collection_name in self._ensure_payload_indexes_cache:
            return

        # In local embedded mode, Qdrant scans payloads without indexing and emits a UserWarning.
        # Payload indexes are only needed/effective in server/docker (gRPC) mode.
        mode = os.environ.get("QDRANT_MODE", "embedded").strip().lower()
        if mode == "embedded":
            self._ensure_payload_indexes_cache.add(collection_name)
            return

        from qdrant_client.models import PayloadSchemaType

        for field in ("branch", "source_file"):
            try:
                self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass  # Index already exists — safe to ignore

        self._ensure_payload_indexes_cache.add(collection_name)

    def _col(self, branch: str) -> str:
        """Return the Qdrant collection name for this branch, ensuring it exists."""
        name = _safe_collection_name(branch)
        self._ensure_collection(name)
        self._ensure_payload_indexes(name)
        return name

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

        from qdrant_client.models import PointStruct

        col = self._col(branch)

        # Build points — store document text in payload so we can retrieve it later
        points = []
        for i, (doc_id, doc_text, vector, meta) in enumerate(
            zip(ids, documents, embeddings, metadatas)
        ):
            payload = dict(meta)
            payload["_document"] = doc_text  # Stored text (preamble + body)
            payload["_id_str"] = doc_id       # Original string ID for migration back-compat
            points.append(
                PointStruct(
                    id=_str_to_uuid(doc_id),
                    vector=vector,
                    payload=payload,
                )
            )

        # Batch upsert
        for batch_start in range(0, len(points), self.BATCH_SIZE):
            batch = points[batch_start : batch_start + self.BATCH_SIZE]
            self._client.upsert(collection_name=col, points=batch)

        logger.debug("Qdrant: upserted %d chunks for branch '%s'", len(ids), branch)

    def delete_file(self, branch: str, filename: str) -> int:
        """Delete all points whose payload source_file == filename."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        col = _safe_collection_name(branch)
        existing = {c.name for c in self._client.get_collections().collections}
        if col not in existing:
            return 0

        try:
            # Count first so we can return the number deleted
            count_before = self._client.count(
                collection_name=col,
                count_filter=Filter(
                    must=[FieldCondition(key="source_file", match=MatchValue(value=filename))]
                ),
                exact=True,
            ).count

            self._client.delete(
                collection_name=col,
                points_selector=Filter(
                    must=[FieldCondition(key="source_file", match=MatchValue(value=filename))]
                ),
            )
            logger.info(
                "Qdrant: deleted %d chunks for file '%s' in collection '%s'",
                count_before, filename, col,
            )
            return count_before
        except Exception as exc:
            logger.warning("Qdrant delete_file error: %s", exc)
            return 0

    # ── Read Operations ─────────────────────────────────────────────────────────

    def query(
        self,
        branch: str,
        query_embedding: List[float],
        top_k: int = 20,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Dense cosine similarity search.

        Returns a ChromaDB-compatible dict:
            { "ids": [[...]], "documents": [[...]], "metadatas": [[...]], "distances": [[...]] }
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        col = _safe_collection_name(branch)
        existing = {c.name for c in self._client.get_collections().collections}
        if col not in existing:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        query_filter = None
        if where:
            # Simple equality filters — extend for complex operators if needed
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in where.items()
                if isinstance(v, (str, int, float, bool))
            ]
            if conditions:
                query_filter = Filter(must=conditions)

        if hasattr(self._client, "query_points"):
            response = self._client.query_points(
                collection_name=col,
                query=query_embedding,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )
            results = response.points
        else:
            results = self._client.search(
                collection_name=col,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )

        ids, docs, metas, dists = [], [], [], []
        for hit in results:
            payload = hit.payload or {}
            ids.append(payload.get("_id_str", str(hit.id)))
            docs.append(payload.get("_document", ""))
            # Return metadata without internal fields
            meta = {k: v for k, v in payload.items() if not k.startswith("_")}
            metas.append(meta)
            # Qdrant returns cosine similarity score [0,1]; convert to distance for compat
            dists.append(1.0 - hit.score)

        return {
            "ids": [ids],
            "documents": [docs],
            "metadatas": [metas],
            "distances": [dists],
        }

    def get_all(
        self,
        branch: str,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Scroll through all points in the branch collection."""
        col = _safe_collection_name(branch)
        existing = {c.name for c in self._client.get_collections().collections}
        if col not in existing:
            return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

        inc = set(include or ["documents", "metadatas"])
        with_vectors = "embeddings" in inc

        ids, docs, metas, vecs = [], [], [], []
        offset = None

        while True:
            batch, next_offset = self._client.scroll(
                collection_name=col,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=with_vectors,
            )
            for point in batch:
                payload = point.payload or {}
                ids.append(payload.get("_id_str", str(point.id)))
                docs.append(payload.get("_document", ""))
                meta = {k: v for k, v in payload.items() if not k.startswith("_")}
                metas.append(meta)
                if with_vectors and point.vector is not None:
                    vecs.append(point.vector)

            if next_offset is None:
                break
            offset = next_offset

        result: Dict[str, Any] = {"ids": ids, "documents": docs, "metadatas": metas}
        if with_vectors:
            result["embeddings"] = vecs
        return result

    # ── Utility ─────────────────────────────────────────────────────────────────

    def collection_exists(self, branch: str) -> bool:
        col = _safe_collection_name(branch)
        return col in {c.name for c in self._client.get_collections().collections}

    def count(self, branch: str) -> int:
        col = _safe_collection_name(branch)
        existing = {c.name for c in self._client.get_collections().collections}
        if col not in existing:
            return 0
        return self._client.count(collection_name=col, exact=True).count

    def close(self) -> None:
        try:
            if hasattr(self._client, "close"):
                self._client.close()
        except Exception:
            pass


# ── Utility: deterministic string → UUID5 ─────────────────────────────────────

_UUID_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # url namespace


def _str_to_uuid(s: str) -> str:
    """Convert any string ID to a deterministic UUID5 string (Qdrant requires UUID or uint64)."""
    return str(uuid.uuid5(_UUID_NS, s))
