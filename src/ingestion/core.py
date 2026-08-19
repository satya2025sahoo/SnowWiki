"""
src/ingestion/core.py
=====================
ChromaDB client, embedding model, upload directory helpers,
parent-section JSON store, and timestamp parsing utility.
"""

from __future__ import annotations

import json
import os
import re

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import (
    CHROMA_DB_DIR,
    UPLOADS_DIR,
    EMBEDDING_MODEL_NAME,
    COLLECTION_NAME,
    PARENT_STORE_DIR,
)


# ── Singleton embedding model ──────────────────────────────────────────────────

_EMBEDDER: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    """Lazy-load and cache the SentenceTransformer model."""
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _EMBEDDER


def get_chroma_collection():
    """Return (or create) the persistent ChromaDB collection."""
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ── Directory helpers ──────────────────────────────────────────────────────────

def get_branch_upload_dir(branch_name: str) -> str:
    branch_dir = os.path.join(UPLOADS_DIR, branch_name)
    os.makedirs(branch_dir, exist_ok=True)
    return branch_dir


# ── Timestamp Helpers ──────────────────────────────────────────────────────────

def parse_timestamp_str(timestamp_str: str) -> int:
    """Convert 'MM:SS' or 'HH:MM:SS' string into total seconds."""
    parts = timestamp_str.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        pass
    return 0


# ── Parent Store Persistence ───────────────────────────────────────────────────

def _branch_safe(branch_name: str) -> str:
    """Sanitise branch name for use as a filesystem key."""
    return re.sub(r"[^\w\-]", "_", branch_name)


def save_parent_store(branch_name: str, parent_sections: list[dict]) -> None:
    """
    Append new parent sections to the branch's JSON key-value store.
    Keys are parent_id strings; values are parent section dicts.
    """
    store_path = os.path.join(PARENT_STORE_DIR, f"{_branch_safe(branch_name)}.json")
    if os.path.exists(store_path):
        try:
            with open(store_path, "r", encoding="utf-8") as f:
                store: dict = json.load(f)
        except Exception:
            store = {}
    else:
        store = {}

    for ps in parent_sections:
        store[ps["parent_id"]] = ps

    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)


def load_parent_store(branch_name: str) -> dict[str, dict]:
    """Load the branch's parent store JSON. Returns empty dict if not found."""
    store_path = os.path.join(PARENT_STORE_DIR, f"{_branch_safe(branch_name)}.json")
    if not os.path.exists(store_path):
        return {}
    try:
        with open(store_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[ingestion] Failed to load parent store for '{branch_name}': {exc}")
        return {}
