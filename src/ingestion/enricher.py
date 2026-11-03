"""
src/ingestion/enricher.py
=========================
Two-pass image enrichment (v2.0):
Reads a Markdown file, checks SQLite image_assets.db for junk/routing verdicts,
skips VLM for 'ocr_primary', calls VLM for 'ocr_plus_vlm'/'vlm_only' with context,
and enriches the Markdown file.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
from src.ingestion.image_describer import ImageDescriberAgent
from src.ingestion.image_classifier import get_db_path, upsert_asset, _sha256

logger = logging.getLogger(__name__)


def get_asset_by_sha256(sha256: str) -> dict | None:
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Get latest matching sha256
    cursor.execute("SELECT * FROM image_assets WHERE sha256 = ? ORDER BY created_at DESC LIMIT 1", (sha256,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def enrich_markdown_with_images(
    markdown_path: str,
    branch_name: str,
    image_dir: str,
    status_callback=None,
    max_images: int = 15,  # Increased default since junk filtering saves credits
) -> str:
    if not os.path.exists(markdown_path):
        return ""

    with open(markdown_path, "r", encoding="utf-8") as f:
        content = f.read()

    doc_name = os.path.basename(markdown_path)
    img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    env_limit = os.environ.get("MAX_VISION_IMAGES_PER_DOC")
    if env_limit:
        try:
            max_images = int(env_limit)
        except ValueError:
            pass

    image_describer = ImageDescriberAgent(
        image_dir=image_dir,
        document_name=doc_name,
        branch_name=branch_name,
    )

    all_matches = list(img_pattern.finditer(content))
    if not all_matches:
        return content

    call_count = 0
    # Collect context by scanning paragraphs before the image
    # For a simple implementation, we can just pass the OCR text directly for now.

    # Pass 1: Run VLM for missing descriptions
    for idx, match in enumerate(all_matches, start=1):
        if call_count >= max_images:
            break

        rel_path = match.group(2)
        filename = os.path.basename(rel_path)
        abs_img_path = os.path.join(image_dir, filename)

        if not os.path.exists(abs_img_path):
            continue

        sha = _sha256(abs_img_path)
        asset = get_asset_by_sha256(sha)
        if not asset:
            logger.warning(f"No asset record found for {filename} (sha256: {sha})")
            continue

        if asset["junk"]:
            continue

        if asset["description"]:
            continue  # Already extracted

        if asset["route"] == "ocr_primary":
            asset["description"] = asset["ocr_text"]
            upsert_asset(asset)
            continue

        # Needs VLM
        if status_callback:
            status_callback(f"Analyzing image ({idx}/{len(all_matches)}): {filename}…")

        if call_count > 0:
            time.sleep(1.0)
        call_count += 1

        try:
            raw_desc = image_describer.describe_from_path(
                file_path=abs_img_path,
                image_index=idx,
                rel_path=rel_path,
                ocr_text=asset.get("ocr_text", "")
            )
            desc = raw_desc.strip()
            if desc and "unavailable" not in desc.lower():
                asset["description"] = desc
                upsert_asset(asset)
        except Exception as e:
            logger.warning("VLM call failed for %s: %s", filename, e)

    # Pass 2: Replace text
    def replace_image(match):
        alt_text = match.group(1)
        rel_path = match.group(2)
        filename = os.path.basename(rel_path)
        abs_img_path = os.path.join(image_dir, filename)

        if not os.path.exists(abs_img_path):
            return match.group(0)

        sha = _sha256(abs_img_path)
        asset = get_asset_by_sha256(sha)
        
        if not asset:
            return f"![Image]({rel_path})"

        # If junk, just keep a clean tag (or strip it, but let's keep it to avoid messing up markdown flow entirely)
        if asset["junk"]:
            return f"![Image]({rel_path})"
        
        desc = asset.get("description", "")
        # Inject the short ID into the Markdown so chunking.py can find it!
        image_id = asset.get("image_id", "")
        
        if desc and "unavailable" not in desc.lower() and "error" not in desc.lower():
            # We encode the image_id inside the alt-text or title so chunking.py can extract it easily.
            # Using: ![IMG_7f3a](images/img.png)
            enriched = f"![{image_id}]({rel_path})\n\n> **Visual Analysis:**\n"
            for line in desc.splitlines():
                line_str = line.strip()
                if line_str:
                    enriched += f"> {line_str}\n"
                else:
                    enriched += ">\n"
            return enriched

        return f"![{image_id}]({rel_path})"

    new_content = img_pattern.sub(replace_image, content)

    # ── Evict Vision Model from GPU VRAM ──────────────────────────────────────
    # Releases the ~6.5 GB VLM so the 7B/8B text model has full headroom
    if os.environ.get("VISION_LLM_PROVIDER", "").lower() == "local":
        from src.llm_wrapper import unload_local_model
        vlm_model = os.environ.get("LOCAL_VISION_MODEL", "qwen3-vl:8b")
        unload_local_model(vlm_model)

    if new_content != content:
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return new_content
