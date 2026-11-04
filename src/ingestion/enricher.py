"""
src/ingestion/enricher.py
=========================
Two-phase visual asset pipeline:
Phase 1:
  - Classifies extracted images, runs junk filtering.
  - Generates VLM visual analysis (cached in SQLite image_assets.db).
  - Saves full analysis into transparent `image_manifest.json` in the document folder.
  - Replaces image tags with clean, lightweight anchors: `![IMG_xxxx](images/...)`.
  - Unloads VLM from GPU VRAM.

Phase 2 (Post-Rolling Rewrite):
  - Deterministically matches each `![IMG_xxxx]` anchor in the final restructured Markdown
    and appends the full `> **Visual Analysis:**` block.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sqlite3
import time
from typing import Any

from src.ingestion.image_describer import ImageDescriberAgent
from src.ingestion.image_classifier import (
    get_db_path,
    upsert_asset,
    _sha256,
    classify_image,
    build_phash_doc_counts,
)

logger = logging.getLogger(__name__)


def get_asset_by_sha256(sha256: str) -> dict | None:
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM image_assets WHERE sha256 = ? ORDER BY created_at DESC LIMIT 1",
        (sha256,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ── Phase 1: Visual Asset Extraction & Manifest Generation ─────────────────────

def generate_image_manifest(
    markdown_path: str,
    branch_name: str,
    image_dir: str,
    status_callback=None,
    max_images: int = 30,
) -> tuple[dict[str, Any], str]:
    """
    1. Discovers all images referenced in markdown_path or residing in image_dir.
    2. Runs junk filter & OCR/VLM description (caching in SQLite).
    3. Writes transparent `image_manifest.json` in image_dir and document folder.
    4. Replaces images in markdown_path with clean lightweight anchors: `![IMG_xxxx](images/...)`.
    5. Evicts VLM from GPU VRAM.

    Returns:
        (manifest_dict, clean_anchor_markdown)
    """
    if not os.path.exists(markdown_path):
        return {}, ""

    with open(markdown_path, "r", encoding="utf-8") as f:
        content = f.read()

    doc_name = os.path.basename(markdown_path)
    doc_dir = os.path.dirname(markdown_path)
    img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    env_limit = os.environ.get("MAX_VISION_IMAGES_PER_DOC")
    if env_limit:
        try:
            max_images = int(env_limit)
        except ValueError:
            pass

    # Gather extracted images
    image_files = []
    if os.path.exists(image_dir):
        image_files = [
            f for f in os.listdir(image_dir)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
        ]

    # Pre-build phash counts for duplicate detection
    doc_phash_counts = build_phash_doc_counts({
        doc_name: [os.path.join(image_dir, f) for f in image_files]
    })

    image_describer = ImageDescriberAgent(
        image_dir=image_dir,
        document_name=doc_name,
        branch_name=branch_name,
    )

    manifest: dict[str, Any] = {
        "document": doc_name,
        "branch": branch_name,
        "generated_at": datetime.datetime.now().isoformat(),
        "total_images": len(image_files),
        "images": {},
        "by_id": {},
    }

    call_count = 0
    for idx, img_file in enumerate(image_files, start=1):
        abs_img_path = os.path.join(image_dir, img_file)
        rel_path = f"images/{img_file}"
        sha = _sha256(abs_img_path)

        # 1. Classify image & check junk
        verdict = classify_image(abs_img_path, doc_phash_counts)
        asset = get_asset_by_sha256(sha)

        if not asset:
            asset = {
                "sha256": sha,
                "context_hash": "",
                "model_version": "",
                "prompt_version": "v2.0",
                "junk": verdict.junk,
                "reason": verdict.reason,
                "route": verdict.route,
                "ocr_text": verdict.ocr_text,
                "description": "",
                "doc_id": doc_name,
                "branch": branch_name,
                "image_id": verdict.image_id,
                "rel_path": rel_path,
                "abs_path": abs_img_path,
                "page": 1,
                "parent_id": "",
            }
            upsert_asset(asset)

        image_id = asset.get("image_id") or verdict.image_id
        is_junk = asset.get("junk", verdict.junk)
        desc = asset.get("description", "")

        # 2. Run VLM if valid non-junk image and missing description
        if not is_junk and not desc and call_count < max_images:
            if asset.get("route") == "ocr_primary" and asset.get("ocr_text"):
                desc = asset["ocr_text"]
                asset["description"] = desc
                upsert_asset(asset)
            else:
                if status_callback:
                    status_callback(f"Analyzing visual asset ({idx}/{len(image_files)}): {img_file}…")
                if call_count > 0:
                    time.sleep(1.0)
                call_count += 1
                try:
                    raw_desc = image_describer.describe_from_path(
                        file_path=abs_img_path,
                        image_index=idx,
                        rel_path=rel_path,
                        ocr_text=asset.get("ocr_text", ""),
                    )
                    clean_vlm = raw_desc.strip()
                    if clean_vlm and "unavailable" not in clean_vlm.lower() and "error" not in clean_vlm.lower():
                        desc = clean_vlm
                        asset["description"] = desc
                        upsert_asset(asset)
                except Exception as exc:
                    logger.warning("VLM call failed for %s: %s", img_file, exc)

        # Populate manifest entry
        entry = {
            "image_id": image_id,
            "filename": img_file,
            "rel_path": rel_path,
            "sha256": sha,
            "junk": bool(is_junk),
            "reason": asset.get("reason", verdict.reason),
            "route": asset.get("route", verdict.route),
            "ocr_text": asset.get("ocr_text", ""),
            "visual_analysis": desc,
        }
        manifest["images"][img_file] = entry
        manifest["by_id"][image_id] = entry

    # 3. Save image_manifest.json in image_dir and doc_dir for transparency
    manifest_paths = [
        os.path.join(image_dir, "image_manifest.json"),
        os.path.join(doc_dir, "image_manifest.json"),
    ]
    for m_path in manifest_paths:
        try:
            with open(m_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            logger.info("Saved image manifest to %s", m_path)
        except Exception as exc:
            logger.warning("Failed to save image manifest to %s: %s", m_path, exc)

    # 4. Replace image tags in raw Markdown with clean lightweight anchors
    def _replace_with_anchor(match: re.Match) -> str:
        rel_path = match.group(2).replace("\\", "/")
        filename = os.path.basename(rel_path)
        info = manifest["images"].get(filename)

        if not info:
            # Check by matching basename
            for f_name, i_data in manifest["images"].items():
                if f_name.lower() == filename.lower():
                    info = i_data
                    break

        if not info:
            return match.group(0)

        if info["junk"]:
            return f"<!-- Decorative image {filename} omitted -->"

        img_id = info["image_id"]
        return f"![{img_id}]({info['rel_path']})"

    clean_content = img_pattern.sub(_replace_with_anchor, content)

    # 5. Evict Vision Model from GPU VRAM
    if os.environ.get("VISION_LLM_PROVIDER", "").lower() == "local":
        from src.llm_wrapper import unload_local_model
        vlm_model = os.environ.get("LOCAL_VISION_MODEL", "minicpm-v")
        unload_local_model(vlm_model)

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(clean_content)

    return manifest, clean_content


# ── Phase 3: Post-Rolling Deterministic Visual Analysis Insertion ─────────────

def inject_visual_analysis_into_markdown(
    markdown_path: str,
    manifest: dict[str, Any] | str | None = None,
) -> str:
    """
    Runs AFTER the rolling LLM text restructuring finishes.
    Deterministically matches `![IMG_xxxx](...)` anchors in the restructured Markdown
    and appends the clean `> **Visual Analysis:**` block directly beneath each image.
    """
    if not os.path.exists(markdown_path):
        return ""

    doc_dir = os.path.dirname(markdown_path)
    image_dir = os.path.join(doc_dir, "images")

    # Load manifest if not provided
    if isinstance(manifest, str) and os.path.exists(manifest):
        with open(manifest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    elif manifest is None or not isinstance(manifest, dict):
        candidate_paths = [
            os.path.join(doc_dir, "image_manifest.json"),
            os.path.join(image_dir, "image_manifest.json"),
        ]
        manifest = {}
        for p in candidate_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    break
                except Exception:
                    pass

    by_id = manifest.get("by_id", {})
    by_filename = manifest.get("images", {})

    with open(markdown_path, "r", encoding="utf-8") as f:
        content = f.read()

    img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    def _inject_analysis(match: re.Match) -> str:
        alt_text = match.group(1).strip()
        rel_path = match.group(2).replace("\\", "/").strip()
        filename = os.path.basename(rel_path)

        info = by_id.get(alt_text) or by_filename.get(filename)
        if not info:
            # Fallback scan in by_id values
            for entry in by_id.values():
                if entry.get("filename", "").lower() == filename.lower():
                    info = entry
                    break

        if not info:
            return match.group(0)

        if info.get("junk"):
            return f"<!-- Decorative image {filename} omitted -->"

        img_id = info.get("image_id", alt_text)
        desc = info.get("visual_analysis") or info.get("description", "")
        desc = desc.strip()

        if not desc or "unavailable" in desc.lower() or "error" in desc.lower():
            return f"![{img_id}]({rel_path})"

        # Build clean blockquote
        enriched = f"![{img_id}]({rel_path})\n\n> **Visual Analysis:**\n"
        for line in desc.splitlines():
            line_str = line.strip()
            if line_str:
                enriched += f"> {line_str}\n"
            else:
                enriched += ">\n"

        return enriched

    final_content = img_pattern.sub(_inject_analysis, content)

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    return final_content


# ── Backward Compatibility Wrapper ────────────────────────────────────────────

def enrich_markdown_with_images(
    markdown_path: str,
    branch_name: str,
    image_dir: str,
    status_callback=None,
    max_images: int = 15,
) -> str:
    """Legacy wrapper: runs manifest generation then injection in one call."""
    manifest, _ = generate_image_manifest(
        markdown_path=markdown_path,
        branch_name=branch_name,
        image_dir=image_dir,
        status_callback=status_callback,
        max_images=max_images,
    )
    return inject_visual_analysis_into_markdown(markdown_path, manifest)
