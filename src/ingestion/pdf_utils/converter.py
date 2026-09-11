"""
src/ingestion/pdf_utils/converter.py
=====================================
Main PDF -> Markdown converter orchestrating all pipeline stages:

  Stage 1: extract_pdf_elements()     — pdfplumber .chars + pypdf images
  Stage 1.5: Document-level guard rail — fail loudly on near-zero text
  Stage 2: clean_pdf_text_block()     — PDF pathology fixes (dehyphen, kerning)
  Stage 3: _classify_and_emit()       — relative heading detection (D2) +
                                        inline image placement (D3) +
                                        table injection
  Stage 4: _normalize_markdown_common() — two-pass shared normalizer
"""

from __future__ import annotations

import os
import re
import unicodedata
import logging
from collections import Counter

# Module-level imports so tests can patch via the converter module's namespace
from src.ingestion.pdf_utils.extraction import extract_pdf_elements
from src.ingestion.pdf_utils.pre_cleaner import clean_pdf_text_block
from src.ingestion.pdf_utils.tables import extract_page_tables, get_table_bboxes
from src.ingestion.docx_utils.normalization import _normalize_markdown_common
from src.ingestion.core import get_branch_image_dir

logger = logging.getLogger(__name__)

# ── Document-level guard rail ─────────────────────────────────────────────────
MIN_TEXT_CHARS = 100  # tunable constant


# ── D2: Relative heading detection ────────────────────────────────────────────

def _compute_body_size(text_pages) -> float:
    """
    Compute the body font size as the size with the highest TOTAL CHARACTER COVERAGE.

    Sanity check (D2): if the modal size accounts for < 40% of all chars,
    the distribution is too flat (title-slides, outline-heavy decks) — log a WARNING
    and still use the best available estimate.
    """
    size_char_counts: dict[float, int] = {}
    for page_blocks in text_pages:
        for block in page_blocks:
            s = round(block.avg_size * 2) / 2  # round to nearest 0.5pt
            size_char_counts[s] = size_char_counts.get(s, 0) + len(block.text)

    if not size_char_counts:
        return 10.0

    total_chars = sum(size_char_counts.values())
    sorted_by_coverage = sorted(size_char_counts.items(), key=lambda x: x[1], reverse=True)
    modal_size, modal_count = sorted_by_coverage[0]
    coverage = modal_count / total_chars if total_chars else 0.0

    if coverage < 0.40:
        logger.warning(
            "PDF heading detection uncertain — modal body size %.1fpt has coverage %.0f%% "
            "(< 40%%). Document may be a title-slide deck or dense outline; "
            "heading classification results may be degraded.",
            modal_size, coverage * 100,
        )
        # Fallback: largest cluster by total character count (already sorted that way)
        # No change to modal_size — it IS the largest by char count

    return modal_size


def _classify_block(block, body_size: float) -> str:
    """
    Classify a TextBlock into a Markdown element string using D2 relative thresholds.

    Thresholds (relative to body_size):
      >= 1.5x  -> # H1
      >= 1.2x  -> ## H2
      >= 1.05x AND bold -> ### H3
      bold AND short (<= 12 words) AND not bullet -> ## H2  [Fix 3: same-size bold headings]
      starts with bullet chars (extended set) -> - item      [Fix 4: Unicode bullets]
      ServiceNow code -> ```javascript ... ```
      else -> paragraph text
    """
    from src.ingestion.docx_utils.heuristics import _is_servicenow_code

    text = block.text.strip()
    if not text:
        return ""

    size = block.avg_size

    # Heading thresholds (size-based)
    if size >= body_size * 1.5:
        return f"\n# {text}\n"
    if size >= body_size * 1.2:
        return f"\n## {text}\n"
    if size >= body_size * 1.05 and block.is_bold:
        return f"\n### {text}\n"

    # Fix 4: Extended bullet character set — includes Unicode private-use glyphs
    # that pdfplumber emits for common PDF bullet symbols (■ ▪ ◆ \uf0b7 \uf0a7)
    _BULLET_CHARS = ("\u2022", "\u25cf", "-", "*", "\u2013", "\u25aa", "\u25a0", "\u25c6", "\uf0b7", "\uf0a7")
    is_bullet = text.startswith(_BULLET_CHARS) or (
        len(text) > 1 and unicodedata.category(text[0]) in ("So", "Po")
        and not text[0].isalpha()
    )
    if is_bullet:
        clean = re.sub(r"^[\u2022\u25cf\-\*\u2013\u25aa\u25a0\u25c6\uf0b7\uf0a7\s]+", "", text)
        return f"- {clean}"

    # Fix 3: Bold-only heading tier — same body size but bold and short = section heading
    # Guard: <= 12 words prevents long bold paragraphs (key-takeaways etc.) becoming headings
    if block.is_bold and len(text.split()) <= 12:
        return f"\n## {text}\n"

    # ServiceNow code auto-fencing
    if _is_servicenow_code(text):
        return f"\n```javascript\n{text}\n```\n"

    return text


# ── D3: Inline image placement ─────────────────────────────────────────────────

def _place_images_inline(
    ordered_blocks,
    image_blocks,
    is_multi_column: bool,
) -> list[str]:
    """
    D3 algorithm: place image markdown refs inline between text blocks.

    Coordinate convention: pdfplumber top-left origin, y INCREASES downward.
    Ascending y0 = top-to-bottom reading order.

    Rules:
      1. Sort all elements by (y0, x0).
      2. For each image, insert its ref after the last text block whose y1 <= image.y0.
      3. Tie-break / overlap: if image.y0 falls inside a text block's y-range
         AND x-ranges overlap, treat image as starting AFTER that block.
      4. Multi-column fallback: append images at page-end with HTML comment.
      5. No-layout fallback: if any image has y0 == 0 and x0 == 0 (no bbox data),
         append at page-end with WARNING comment.
    """
    if not image_blocks:
        return [b.text_md for b in ordered_blocks] if hasattr(ordered_blocks[0], "text_md") else []

    # Convert text block list to (text_md, block) pairs
    block_items = list(ordered_blocks)  # already sorted TextBlock list

    if is_multi_column:
        # Multi-column: emit text first, then images at end with comment
        text_lines = [b.text_md for b in block_items if hasattr(b, "text_md")]
        for img in image_blocks:
            text_lines.append(f"\n![{img.filename}]({img.rel_path})")
            text_lines.append("<!-- image position approximate: multi-column page -->")
        return text_lines

    # Check if any image lacks valid bbox (no-layout fallback)
    def _has_valid_bbox(img) -> bool:
        return not (img.x0 == 0.0 and img.top == 0.0 and img.x1 == 0.0 and img.bottom == 0.0)

    # Build output by inserting images at correct positions
    # Walk through text blocks and insert images when their top <= current block's top
    result: list[str] = []
    images_remaining = sorted(image_blocks, key=lambda im: im.top)
    img_idx = 0

    for block in block_items:
        # Insert all images whose position is above this block (top <= block.top)
        while img_idx < len(images_remaining):
            img = images_remaining[img_idx]

            if not _has_valid_bbox(img):
                # No-layout fallback
                logger.warning(
                    "Image '%s' has no bounding box — appending at page end.", img.filename
                )
                result.append(f"\n![{img.filename}]({img.rel_path})")
                result.append("<!-- PDF: image position unavailable -->")
                img_idx += 1
                continue

            # D3 rule 2: insert after last text block whose bottom <= image.top
            # D3 rule 3 overlap: image.top inside block's y-range AND x-ranges overlap
            x_overlap = (img.x0 < block.x1) and (img.x1 > block.x0)
            y_overlap = block.top <= img.top < block.bottom

            if y_overlap and x_overlap:
                # Image overlaps this block — defer until after this block
                break
            elif img.top <= block.top:
                # Image is above this block — insert before it
                result.append(f"\n![{img.filename}]({img.rel_path})\n")
                img_idx += 1
            else:
                # Image is below this block — move to next block
                break

        md = getattr(block, "text_md", "")
        if md:
            result.append(md)

    # Append any remaining images after all text blocks
    while img_idx < len(images_remaining):
        img = images_remaining[img_idx]
        result.append(f"\n![{img.filename}]({img.rel_path})\n")
        img_idx += 1

    return result



# ── Table region filtering ─────────────────────────────────────────────────────

def _block_in_table_region(block, table_bboxes: list) -> bool:
    """Return True if the block's bbox overlaps any known table bounding box."""
    for (tx0, ty0, tx1, ty1) in table_bboxes:
        if block.x0 < tx1 and block.x1 > tx0 and block.top < ty1 and block.bottom > ty0:
            return True
    return False



# ── Main converter ─────────────────────────────────────────────────────────────

def _convert_pdf_pdfplumber(file_path: str, branch_name: str, image_dir: str, prefix: str) -> str:
    """
    Fallback pipeline:
      1. Extract text blocks + images (pdfplumber .chars + pypdf)
      1.5 Document-level near-zero-text guard rail
      2. PDF-specific pre-cleaning per block (dehyphen, kerning, linebreak join)
      3. Relative heading classification (D2) + inline image placement (D3)
         + table injection
      4. Two-pass shared normalizer (_normalize_markdown_common)
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required. Run: pip install pdfplumber")

    # ── Stage 1: Extract ──────────────────────────────────────────────────────
    logger.info("PDF extraction starting: %s", file_path)
    text_pages, image_pages, multi_column_flags = extract_pdf_elements(
        file_path, image_dir, prefix=prefix
    )

    # ── Stage 1.5: Document-level guard rail ──────────────────────────────────
    total_text = sum(len(b.text) for page in text_pages for b in page)
    if total_text < MIN_TEXT_CHARS:
        raise ValueError(
            f"PDF '{os.path.basename(file_path)}' yielded only {total_text} characters "
            f"of extracted text (minimum: {MIN_TEXT_CHARS}). "
            "This PDF may be scanned/image-only or corrupted. "
            "OCR ingestion is not supported by this pipeline."
        )

    # ── Stage 2 + 3: Pre-clean, classify, place images ────────────────────────
    body_size = _compute_body_size(text_pages)
    logger.info("PDF body_size=%.1fpt for %s", body_size, os.path.basename(file_path))

    all_md_lines: list[str] = []

    with pdfplumber.open(file_path) as pdf:
        for page_num, (page_blocks, image_blocks, is_mc) in enumerate(
            zip(text_pages, image_pages, multi_column_flags), start=1
        ):
            pdfplumber_page = pdf.pages[page_num - 1]

            # Get table bounding boxes to skip text inside table regions
            try:
                table_bboxes = get_table_bboxes(pdfplumber_page)
            except Exception:
                table_bboxes = []

            # Extract and append tables for this page
            try:
                page_table_mds = extract_page_tables(pdfplumber_page)
            except Exception as e:
                logger.warning("Table extraction failed on page %d: %s", page_num, e)
                page_table_mds = []

            # Attach classified markdown text to each block (for D3 interleaving)
            classified_blocks = []
            for block in page_blocks:
                # Skip text blocks that fall inside a table region
                if table_bboxes and _block_in_table_region(block, table_bboxes):
                    continue

                # Stage 2: pre-clean
                block.text = clean_pdf_text_block(block.text)
                if not block.text:
                    continue

                # Stage 3: classify
                md_line = _classify_block(block, body_size)
                block.text_md = md_line  # attach for D3 use
                if md_line:
                    classified_blocks.append(block)

            # D3: inline image placement
            if classified_blocks:
                page_lines = _place_images_inline(
                    classified_blocks, image_blocks, is_mc
                )
                all_md_lines.extend(page_lines)
            elif image_blocks:
                # Page had only images (e.g. a figure page)
                for img in image_blocks:
                    all_md_lines.append(f"\n![{img.filename}]({img.rel_path})\n")

            # Append tables after page text
            for table_md in page_table_mds:
                all_md_lines.append(f"\n{table_md}\n")

    # ── Stage 4: Shared normalizer ────────────────────────────────────────────
    # Fix 5: Blank-line-aware assembly so RAG chunkers find \n\n block boundaries.
    # Insert a blank line before/after headings and between non-bullet prose blocks.
    assembled: list[str] = []
    for line in all_md_lines:
        stripped = line.strip()
        is_heading = stripped.startswith("#")
        is_blank   = stripped == ""

        # Ensure heading is preceded by a blank line
        if is_heading and assembled and assembled[-1].strip() != "":
            assembled.append("")

        assembled.append(line)

        # Ensure heading is followed by a blank line
        if is_heading:
            assembled.append("")

    raw_md = "\n".join(assembled)
    return _normalize_markdown_common(raw_md)


def convert_pdf_to_markdown(
    file_path: str,
    branch_name: str = "default",
    image_dir: str | None = None,
) -> str:
    """
    Convert a PDF file to structured Markdown.
    Primary engine: pymupdf4llm
    Fallback engine: pdfplumber pipeline

    Args:
        file_path:   Absolute path to the PDF.
        branch_name: Session/branch name (used to locate image dir if image_dir is None).
        image_dir:   Optional explicit directory for extracted images. When supplied
                     (e.g., the file's own per-file subdirectory), images are written
                     there instead of the shared branch images/ folder.
    """
    raw_prefix = os.path.splitext(os.path.basename(file_path))[0]
    prefix = re.sub(r"[^\w\-]+", "_", raw_prefix).strip("_")

    # Resolve image directory — prefer explicit, fall back to branch-level shared dir
    if image_dir is None:
        image_dir = get_branch_image_dir(branch_name)
    else:
        os.makedirs(image_dir, exist_ok=True)

    # Attempt primary engine: marker-pdf (datalab-to/marker)
    try:
        from src.ingestion.pdf_utils.marker_converter import convert_pdf_with_marker
        logger.info(f"Using marker-pdf for {file_path}")
        md_text = convert_pdf_with_marker(
            file_path=file_path,
            image_dir=image_dir,
            image_rel_prefix="images/",
        )
        if md_text and len(md_text.strip()) >= MIN_TEXT_CHARS:
            return md_text
        else:
            logger.warning(
                "marker-pdf extracted < %d chars, falling back to pymupdf4llm",
                MIN_TEXT_CHARS,
            )
    except ImportError as e:
        logger.info("marker-pdf not available (%s), falling back to pymupdf4llm", e)
    except Exception as e:
        logger.warning(
            "marker-pdf failed for '%s': %s. Falling back to pymupdf4llm.",
            file_path,
            e,
        )

    # Attempt secondary engine: pymupdf4llm
    try:
        import pymupdf4llm
        logger.info(f"Using pymupdf4llm for {file_path}")
        md_text = pymupdf4llm.to_markdown(
            file_path,
            write_images=True,
            image_path=image_dir,
            image_format="png"
        )
        if md_text and len(md_text.strip()) >= MIN_TEXT_CHARS:
            # We skip the heavy TwoPassDocumentNormalizer since pymupdf4llm
            # already structures headings and tables correctly.
            # Replace absolute image paths with relative paths
            md_text = md_text.replace(image_dir + os.sep, "images/")
            md_text = md_text.replace(image_dir + "/", "images/")
            return md_text
        else:
            logger.warning(f"pymupdf4llm extracted < {MIN_TEXT_CHARS} chars, falling back to pdfplumber")
    except ImportError:
        logger.info("pymupdf4llm not installed, using pdfplumber fallback")
    except Exception as e:
        logger.warning(f"pymupdf4llm failed: {e}, falling back to pdfplumber")

    # Fall back to pdfplumber
    return _convert_pdf_pdfplumber(file_path, branch_name, image_dir, prefix)
