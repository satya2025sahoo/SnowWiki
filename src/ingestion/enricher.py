"""
src/ingestion/enricher.py
=========================
Two-pass image enrichment:
Reads a Markdown file, finds images with 'VLM_DESC_PENDING',
calls the VLM sequentially one-by-one with caching and rate-limit throttling
for up to `max_images` (default 3 to preserve free API credits),
and enriches the Markdown file with structured descriptions in blockquotes.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from src.ingestion.image_describer import ImageDescriberAgent

logger = logging.getLogger(__name__)


def enrich_markdown_with_images(
    markdown_path: str,
    branch_name: str,
    image_dir: str,
    status_callback=None,
    max_images: int = 3,
) -> str:
    """
    Scans the Markdown file for images.
    Sequentially processes up to `max_images` with VLM (default: 3 to save credits),
    caches the output, and replaces image tags with structured visual descriptions.
    Images beyond `max_images` are preserved as clean Markdown image tags without API calls.
    """
    if not os.path.exists(markdown_path):
        return ""

    with open(markdown_path, "r", encoding="utf-8") as f:
        content = f.read()

    doc_name = os.path.basename(markdown_path)
    img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    # Allow environment override if desired
    env_limit = os.environ.get("MAX_VISION_IMAGES_PER_DOC")
    if env_limit:
        try:
            max_images = int(env_limit)
        except ValueError:
            pass

    # Initialize the image describer
    image_describer = ImageDescriberAgent(
        image_dir=image_dir,
        document_name=doc_name,
        branch_name=branch_name,
    )

    # Setup / load vision cache
    cache_path = os.path.join(image_dir, "vision_cache.json")
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception as e:
            logger.warning("Could not read vision_cache.json: %s", e)

    # Find all image occurrences first
    all_matches = list(img_pattern.finditer(content))
    if not all_matches:
        return content

    # Process up to max_images one-by-one with VLM
    call_count = 0
    for idx, match in enumerate(all_matches, start=1):
        if idx > max_images:
            logger.info("Image %d exceeds max_images limit (%d) — skipping VLM call to save credits.", idx, max_images)
            continue

        rel_path = match.group(2)
        filename = os.path.basename(rel_path)
        abs_img_path = os.path.join(image_dir, filename)

        if not os.path.exists(abs_img_path):
            continue

        desc = cache.get(filename)
        if not desc or "unavailable" in desc.lower() or "error" in desc.lower():
            if status_callback:
                status_callback(f"Analyzing image ({idx}/{min(len(all_matches), max_images)}): {filename}…")

            # 1-second throttle between calls to prevent rate limits
            if call_count > 0:
                time.sleep(1.0)
            call_count += 1

            try:
                raw_desc = image_describer.describe_from_path(
                    file_path=abs_img_path,
                    image_index=idx,
                    rel_path=rel_path,
                )
                desc = raw_desc.strip()
                if desc and "unavailable" not in desc.lower():
                    cache[filename] = desc
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(cache, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning("VLM call failed for %s: %s", filename, e)

    # Now perform the text replacement cleanly
    def replace_image(match):
        alt_text = match.group(1)
        rel_path = match.group(2)
        filename = os.path.basename(rel_path)
        abs_img_path = os.path.join(image_dir, filename)

        if not os.path.exists(abs_img_path):
            return match.group(0)

        desc = cache.get(filename)
        short_alt = "Image" if alt_text in ("VLM_DESC_PENDING", "") else alt_text

        # If we have a valid VLM description in cache, inject the blockquote
        if desc and "unavailable" not in desc.lower() and "error" not in desc.lower():
            enriched = f"![{short_alt}]({rel_path})\n\n> **Visual Analysis:**\n"
            for line in desc.splitlines():
                line_str = line.strip()
                if line_str:
                    enriched += f"> {line_str}\n"
                else:
                    enriched += ">\n"
            return enriched

        # Otherwise just return clean image tag without pending placeholder
        return f"![{short_alt}]({rel_path})"

    new_content = img_pattern.sub(replace_image, content)

    if new_content != content:
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return new_content
