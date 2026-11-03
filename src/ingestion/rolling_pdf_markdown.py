"""
src/ingestion/rolling_pdf_markdown.py
=====================================
Production-grade PDF to Markdown converter using PyMuPDF / pymupdf4llm
and Rolling LLM restructuring with contextual summary feedback.

Features:
- 100% digital text extraction (no OCR dropouts or bounding-box truncation)
- Native embedded image extraction into images/ folder
- Perceptual hash (pHash) junk filtering + SQLite registration (IMG_xxxx)
- Multi-modal diagram enrichment (ImageDescriberAgent)
- Page-by-page rolling LLM restructuring with:
    * Active heading stack tracking (# / ## / ###)
    * Table continuation across page splits (no duplicate headers)
    * Running 15-bullet rolling summary feedback
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from typing import Callable, Optional, Tuple

import pymupdf4llm

from src.llm_wrapper import get_chat_client
from src.ingestion.image_classifier import (
    build_phash_doc_counts,
    classify_image,
    upsert_asset,
)
from src.ingestion.image_describer import ImageDescriberAgent
from src.ingestion.rolling_doc_markdown import _atomic_write, _run_llm_for_page

logger = logging.getLogger(__name__)


def process_pdf_rolling_markdown(
    pdf_path: str,
    output_md_path: str,
    image_dir: Optional[str] = None,
    branch_name: str = "default",
    max_pages: Optional[int] = None,
    status_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[str, str, str]:
    """
    Convert a PDF into structured Markdown using PyMuPDF and Rolling LLM.

    Args:
        pdf_path: Path to the input PDF file.
        output_md_path: Path where the cleaned Markdown should be saved.
        image_dir: Directory where extracted images should be placed.
                   Defaults to a sibling 'images/' folder next to output_md_path.
        branch_name: Active branch/session name.
        max_pages: Optional cap on the number of pages to process.
        status_callback: Optional callback for UI / progress reporting.

    Returns:
        (output_md_path, summary_md_path, full_clean_markdown)
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    doc_name = os.path.basename(pdf_path)
    output_dir = os.path.dirname(os.path.abspath(output_md_path))
    os.makedirs(output_dir, exist_ok=True)

    if image_dir is None:
        image_dir = os.path.join(output_dir, "images")
    os.makedirs(image_dir, exist_ok=True)

    if status_callback:
        status_callback(f"Extracting digital text and images from {doc_name}…")

    # ── Stage 1: Native Extraction via pymupdf4llm ────────────────────────────
    # Extracts page text, native tables, and saves embedded images.
    # NOTE: pymupdf4llm uses Path.cwd() as the base for relative image refs in
    # markdown text.  We temporarily chdir to output_dir so the computed ref is
    # always "images/<file>.png" — an unambiguous relative path that resolves
    # correctly regardless of where the caller invoked us from.
    page_range = None
    if max_pages is not None and max_pages > 0:
        page_range = list(range(max_pages))

    _prev_cwd = os.getcwd()
    try:
        os.chdir(output_dir)
        chunks = pymupdf4llm.to_markdown(
            pdf_path,
            pages=page_range,
            page_chunks=True,
            write_images=True,
            image_path=image_dir,
            image_format="png",
        )
    finally:
        os.chdir(_prev_cwd)

    # Normalize any absolute or unusual image paths in chunk text to
    # "images/<basename>" so later stages can reliably parse them.
    _img_ref_re = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    def _normalize_img_ref(m: re.Match) -> str:
        alt, path = m.group(1), m.group(2)
        basename = os.path.basename(path.replace("\\", "/"))
        return f"![{alt}](images/{basename})"

    for chunk in chunks:
        if isinstance(chunk, dict) and "text" in chunk:
            chunk["text"] = _img_ref_re.sub(_normalize_img_ref, chunk["text"])

    total_chunks = len(chunks)
    logger.info("Extracted %d page chunks from %s", total_chunks, doc_name)

    # ── Stage 2: Image Classification, Junk Filter & SQLite Registration ─────
    extracted_images = [
        f for f in os.listdir(image_dir)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
    ]
    doc_phash_counts = build_phash_doc_counts({
        doc_name: [os.path.join(image_dir, f) for f in extracted_images]
    })

    describer = ImageDescriberAgent(
        image_dir=image_dir,
        document_name=doc_name,
        branch_name=branch_name,
    )

    image_registry: dict[str, dict] = {}
    for img_file in extracted_images:
        img_abs = os.path.join(image_dir, img_file)
        rel_path = f"images/{img_file}"

        verdict = classify_image(img_abs, doc_phash_counts)
        asset_record = {
            "sha256": verdict.sha256,
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
            "abs_path": img_abs,
            "page": 1,
            "parent_id": "",
        }
        upsert_asset(asset_record)

        desc = ""
        if not verdict.junk:
            try:
                # Uses cached vision_debug.json if available
                desc = describer.describe_from_path(
                    file_path=img_abs,
                    image_index=len(image_registry) + 1,
                    rel_path=rel_path,
                )
            except Exception as v_err:
                logger.warning("Could not generate description for %s: %s", img_file, v_err)

        image_registry[img_file] = {
            "image_id": verdict.image_id,
            "junk": verdict.junk,
            "rel_path": rel_path,
            "description": desc,
        }

    # ── Stage 2c: Evict Vision Model from GPU VRAM ────────────────────────────
    # Releases the ~6.5 GB VLM so the 7B/8B text model can take over GPU memory
    # without exceeding the 8 GB laptop VRAM budget.
    if os.environ.get("VISION_LLM_PROVIDER", "").lower() == "local":
        from src.llm_wrapper import unload_local_model
        vlm_model = os.environ.get("LOCAL_VISION_MODEL", "qwen3-vl:8b")
        unload_local_model(vlm_model)

    # ── Stage 3: Normalize & Enrich Page Chunks ───────────────────────────────
    enriched_page_texts: list[str] = []
    for chunk in chunks:
        raw = chunk.get("text", "")

        # Normalize any absolute paths to relative 'images/'
        raw = re.sub(r'!\[.*?\]\([^)]*[/\\]images[/\\]([^)]+)\)', r'![](images/\1)', raw)

        # Inline structured visual analysis for non-junk images
        for img_file, info in image_registry.items():
            if img_file in raw:
                img_id = info["image_id"]
                rel_path = info["rel_path"]
                pattern = re.compile(r'!\[.*?\]\([^)]*' + re.escape(img_file) + r'\)')

                if info["junk"]:
                    # Strip decorative logos/icons from text so they don't pollute RAG
                    raw = pattern.sub(f'<!-- Decorative image {img_file} omitted -->', raw)
                else:
                    desc_body = info["description"].strip()
                    if desc_body:
                        replacement = (
                            f"\n\n![{img_id}]({rel_path})\n\n"
                            f"* **Visual Analysis ({img_id}):**\n{desc_body}\n"
                        )
                    else:
                        replacement = f"\n\n![{img_id}]({rel_path})\n"
                    raw = pattern.sub(replacement, raw)

        enriched_page_texts.append(raw)

    # ── Stage 4: Rolling LLM Restructuring & Summary Generation ───────────────
    client = get_chat_client()
    active_heading_stack = ""
    prev_page_markdown = ""
    rolling_summary = "None (Start of document)"
    global_toc: list[str] = []
    all_clean_md: list[str] = []

    temp_buffer_path = os.path.join(
        tempfile.gettempdir(), f"temp_prev_page_{os.path.basename(pdf_path)}.md"
    )
    if os.path.exists(temp_buffer_path):
        os.remove(temp_buffer_path)

    for i, raw_page in enumerate(enriched_page_texts):
        page_num = i + 1
        if status_callback:
            status_callback(f"Structuring PDF page {page_num}/{total_chunks} with Rolling LLM…")

        if os.path.exists(temp_buffer_path):
            with open(temp_buffer_path, "r", encoding="utf-8") as f:
                prev_page_markdown = f.read()
        else:
            prev_page_markdown = ""

        clean_md, active_heading_stack, rolling_summary, global_toc = _run_llm_for_page(
            client=client,
            active_heading_stack=active_heading_stack,
            prev_page_markdown=prev_page_markdown,
            current_page_raw=raw_page,
            page_num=page_num,
            global_toc=global_toc,
            current_rolling_summary=rolling_summary,
        )

        _atomic_write(temp_buffer_path, clean_md)
        all_clean_md.append(clean_md)

    if os.path.exists(temp_buffer_path):
        os.remove(temp_buffer_path)

    # ── Stage 5: Save Outputs ─────────────────────────────────────────────────
    full_markdown = "\n\n".join(all_clean_md)
    with open(output_md_path, "w", encoding="utf-8") as out_f:
        out_f.write(full_markdown)

    summary_md_path = output_md_path.replace(".md", "_summary.md")
    with open(summary_md_path, "w", encoding="utf-8") as sum_f:
        sum_f.write("# Document Summary & Topic Overview\n\n")
        sum_f.write(rolling_summary)

    logger.info("Successfully converted PDF %s -> %s", doc_name, output_md_path)
    return output_md_path, summary_md_path, full_markdown
