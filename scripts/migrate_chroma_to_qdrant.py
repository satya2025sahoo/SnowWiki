"""
scripts/migrate_chroma_to_qdrant.py
=====================================
One-shot migration: copies all vectors + payloads from the existing
ChromaDB database (data/chroma_db/) into Qdrant (data/qdrant_storage/).

Safe to run multiple times — already-migrated points are skipped via
deterministic UUID5 IDs (the same ID is generated on re-run, so Qdrant
upsert is idempotent).

Usage (from the project root, inside the venv):
    python scripts/migrate_chroma_to_qdrant.py [--dry-run] [--branch BRANCH]

Options:
    --dry-run       Print what would be migrated without writing to Qdrant.
    --branch BRANCH Migrate only the specified branch (default: all branches).
    --batch  N      Points per upsert batch (default: 250).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# Make sure project root is on the path so src.* imports resolve
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
    except ImportError:
        pass


def _chroma_client():
    import chromadb
    from src.config import CHROMA_DB_DIR, COLLECTION_NAME
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _get_all_branches(collection) -> list[str]:
    """Return a sorted list of unique branch names stored in ChromaDB."""
    try:
        results = collection.get(include=["metadatas"])
        branches = {
            m.get("branch", "")
            for m in results.get("metadatas", [])
            if m.get("branch")
        }
        return sorted(branches)
    except Exception as exc:
        print(f"[migrate] ERROR reading branches from ChromaDB: {exc}")
        return []


def _migrate_branch(
    collection,
    branch: str,
    qdrant_store,
    batch_size: int,
    dry_run: bool,
) -> int:
    """Migrate all chunks for one branch. Returns count of points migrated."""
    print(f"\n[migrate] Branch: '{branch}'")

    try:
        data = collection.get(
            where={"branch": {"$eq": branch}},
            include=["documents", "metadatas", "embeddings"],
        )
    except Exception as exc:
        print(f"[migrate] ERROR fetching branch '{branch}': {exc}")
        return 0

    ids        = data.get("ids", [])
    documents  = data.get("documents", [])
    metadatas  = data.get("metadatas", [])
    raw_emb    = data.get("embeddings")

    if raw_emb is None:
        embeddings = []
    elif hasattr(raw_emb, "tolist"):
        embeddings = raw_emb.tolist()
    else:
        embeddings = [e.tolist() if hasattr(e, "tolist") else e for e in raw_emb]

    if len(ids) == 0:
        print(f"[migrate]   No chunks found -- skipping.")
        return 0

    # Validate embedding presence
    if len(embeddings) != len(ids):
        print(f"[migrate]   WARNING: embeddings missing or count mismatch (emb={len(embeddings)}, ids={len(ids)}) -- skipping.")
        return 0

    print(f"[migrate]   {len(ids)} chunks to migrate.")

    if dry_run:
        print(f"[migrate]   [DRY RUN] Would upsert {len(ids)} points into Qdrant.")
        return len(ids)

    t0 = time.perf_counter()
    qdrant_store.upsert_chunks(
        branch=branch,
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    elapsed = time.perf_counter() - t0

    final_count = qdrant_store.count(branch)
    print(
        f"[migrate]   Done. {len(ids)} migrated in {elapsed:.1f}s. "
        f"Qdrant collection now has {final_count} points."
    )
    return len(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate ChromaDB -> Qdrant")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
    parser.add_argument("--branch", default=None, help="Migrate a single branch only")
    parser.add_argument("--batch", type=int, default=250, help="Batch size (default: 250)")
    args = parser.parse_args()

    _load_env()

    print("=" * 60)
    print(" SnowWiki: ChromaDB -> Qdrant Migration")
    print("=" * 60)
    if args.dry_run:
        print(" MODE: DRY RUN -- no data will be written\n")

    # Source: ChromaDB
    print("[migrate] Connecting to ChromaDB...")
    try:
        chroma_col = _chroma_client()
        total_chroma = chroma_col.count()
        print(f"[migrate] ChromaDB: {total_chroma} total chunks.")
    except Exception as exc:
        print(f"[migrate] FATAL: Cannot open ChromaDB: {exc}")
        sys.exit(1)

    if total_chroma == 0:
        print("[migrate] ChromaDB is empty -- nothing to migrate.")
        sys.exit(0)

    # Destination: Qdrant (embedded)
    print("[migrate] Connecting to Qdrant (embedded mode)...")
    # Force embedded mode for migration
    os.environ.setdefault("QDRANT_MODE", "embedded")
    from src.vector_store.qdrant_store import QdrantVectorStore
    qdrant = QdrantVectorStore()
    print("[migrate] Qdrant ready.\n")

    # Determine branches to migrate
    if args.branch:
        branches = [args.branch]
    else:
        branches = _get_all_branches(chroma_col)
        if not branches:
            print("[migrate] No branches found in ChromaDB metadata.")
            sys.exit(0)
        print(f"[migrate] Found {len(branches)} branch(es): {branches}\n")

    total_migrated = 0
    for branch in branches:
        n = _migrate_branch(
            collection=chroma_col,
            branch=branch,
            qdrant_store=qdrant,
            batch_size=args.batch,
            dry_run=args.dry_run,
        )
        total_migrated += n

    qdrant.close()

    print("\n" + "=" * 60)
    if args.dry_run:
        print(f" DRY RUN complete. Would have migrated {total_migrated} chunks.")
    else:
        print(f" Migration complete. {total_migrated} chunks migrated.")
    print(" Next: set VECTOR_STORE_BACKEND=qdrant in your .env and restart.")
    print("=" * 60)


if __name__ == "__main__":
    main()
