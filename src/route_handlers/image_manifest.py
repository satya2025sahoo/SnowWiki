"""
src/route_handlers/image_manifest.py
====================================
Secure SQLite-based image manifest resolution for retrieved chunks.
"""
from __future__ import annotations

import logging
import os
import sqlite3

logger = logging.getLogger(__name__)


def resolve_image_manifest(
    image_ids: list[str],
    active_branch: str,
    max_images: int = 5,
) -> dict[str, str]:
    """
    Given a list of IMG_xxxx IDs, return {image_id: abs_path} by querying
    SQLite. Only images that belong to `active_branch` and whose junk=0 are
    resolved. Paths are NEVER read from LLM output — only from the DB.
    """
    if not image_ids:
        return {}

    manifest: dict[str, str] = {}
    try:
        from src.ingestion.image_classifier import get_db_path

        db_path = get_db_path()
        if not os.path.exists(db_path):
            return {}

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        seen = set()
        for img_id in image_ids:
            if img_id in seen or len(manifest) >= max_images:
                break
            seen.add(img_id)

            # img_id must start with IMG_ to prevent injection
            if not img_id.startswith("IMG_"):
                continue

            cur.execute(
                """
                SELECT abs_path FROM image_assets
                WHERE image_id = ? AND branch = ? AND junk = 0
                ORDER BY created_at DESC LIMIT 1
                """,
                (img_id, active_branch),
            )
            row = cur.fetchone()
            if row:
                abs_path = row["abs_path"]
                # Path-traversal guard: must exist and be an actual file
                if abs_path and os.path.isfile(abs_path):
                    manifest[img_id] = abs_path
        conn.close()
    except Exception as exc:
        logger.warning("resolve_image_manifest error: %s", exc)

    return manifest
