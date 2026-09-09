"""
src/ingestion/pdf_utils/extraction.py
======================================
Structured text + image extraction from PDF using pdfplumber.

Key findings from D1 spike:
- page.chars provides x0, y0, size, fontname per character (extract_words loses y0)
- pdfplumber uses top-left origin; y0 INCREASES downward (ascending y0 = top-to-bottom)
- extract_tables() works reliably for simple tables
- Bounding boxes are in PDF points (1pt = 1/72 inch)
"""

from __future__ import annotations

import os
import re
import uuid
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

Y_TOLERANCE_PT = 2.0   # tolerance band for header/footer y-coord matching
MIN_COL_GAP_PT = 50.0  # minimum x-gap to detect two-column layout


@dataclass
class TextBlock:
    text: str
    avg_size: float
    is_bold: bool
    x0: float
    top: float      # distance from top edge
    x1: float
    bottom: float   # distance from top edge
    page_num: int   # 1-indexed


@dataclass
class ImageBlock:
    data: bytes
    ext: str
    x0: float
    top: float
    x1: float
    bottom: float
    page_num: int   # 1-indexed
    rel_path: str   # e.g. "images/filename.png"
    filename: str


def _group_chars_into_lines(chars: list[dict], line_tol: float = 3.0) -> list[list[dict]]:
    """
    Group per-character dicts into lines by top proximity.
    Returns list of lines, each line sorted by x0 (left-to-right).
    """
    if not chars:
        return []

    # Sort by top ascending (top-to-bottom), then x0
    chars_sorted = sorted(chars, key=lambda c: (round(c["top"] / line_tol), c["x0"]))

    lines: list[list[dict]] = []
    current_line: list[dict] = [chars_sorted[0]]
    current_y = chars_sorted[0]["top"]

    for c in chars_sorted[1:]:
        if abs(c["top"] - current_y) <= line_tol:
            current_line.append(c)
        else:
            lines.append(current_line)
            current_line = [c]
            current_y = c["top"]
    lines.append(current_line)

    return lines


def _lines_to_text_blocks(lines: list[list[dict]], page_num: int) -> list[TextBlock]:
    """
    Convert grouped char-lines into TextBlocks.
    Adjacent lines with compatible font/size are merged into a single block.
    """
    blocks: list[TextBlock] = []
    for line_chars in lines:
        if not line_chars:
            continue
            
        # Reconstruct text carefully to preserve spaces or infer missing ones
        text_parts = []
        prev_x1 = None
        for c in line_chars:
            char_text = c.get("text", "")
            # If gap between chars is large enough relative to font size, insert space
            if prev_x1 is not None and c["x0"] - prev_x1 > (c.get("size", 10.0) * 0.2):
                if not text_parts[-1].endswith(" ") and not char_text.startswith(" "):
                    text_parts.append(" ")
            text_parts.append(char_text)
            prev_x1 = c.get("x1", c["x0"])
            
        text = "".join(text_parts).strip()
        if not text:
            continue

        sizes = [c["size"] for c in line_chars if c.get("size")]
        avg_size = sum(sizes) / len(sizes) if sizes else 10.0
        
        # Check for bold fonts (handling CID fonts)
        is_bold = any(
            any(k in (c.get("fontname") or "").lower() for k in ("bold", "f2", "heavy", "black", "semibold"))
            for c in line_chars
        )

        x0 = min(c["x0"] for c in line_chars)
        top = min(c["top"] for c in line_chars)
        x1 = max(c["x1"] for c in line_chars if c.get("x1") is not None) if any(c.get("x1") for c in line_chars) else x0 + 10
        bottom = max(c.get("bottom", top + avg_size) for c in line_chars)

        blocks.append(TextBlock(
            text=text,
            avg_size=avg_size,
            is_bold=is_bold,
            x0=x0, top=top, x1=x1, bottom=bottom,
            page_num=page_num,
        ))
    return blocks


def _detect_multi_column(text_blocks: list[TextBlock], page_width: float) -> bool:
    """
    Heuristic: if there is a significant x-gap in the middle of the page
    and blocks cluster on left and right, flag as multi-column.
    """
    if not text_blocks:
        return False
    mid = page_width / 2
    left = [b for b in text_blocks if b.x1 < mid - MIN_COL_GAP_PT / 2]
    right = [b for b in text_blocks if b.x0 > mid + MIN_COL_GAP_PT / 2]
    # Multi-column if both sides have substantial content
    return len(left) >= 3 and len(right) >= 3


def _sort_blocks_reading_order(
    text_blocks: list[TextBlock], is_multi_column: bool, page_width: float
) -> list[TextBlock]:
    """
    Sort text blocks into reading order.
    Single column: ascending top (top to bottom).
    Multi-column: sort by (x_band, top) — left column first, then right.
    """
    if not is_multi_column:
        return sorted(text_blocks, key=lambda b: (b.top, b.x0))
    mid = page_width / 2
    return sorted(text_blocks, key=lambda b: (0 if b.x0 < mid else 1, b.top))


def _strip_headers_footers(
    all_page_blocks: list[list[TextBlock]], num_pages: int
) -> list[list[TextBlock]]:
    """
    Remove repeated header/footer text: blocks whose text AND approximate top
    appear on >= 50% of pages (within Y_TOLERANCE_PT).
    """
    if num_pages < 2:
        return all_page_blocks

    threshold = max(2, num_pages // 2)

    # Build candidate map: text -> list of top values across pages
    from collections import defaultdict
    text_y_map: dict[str, list[float]] = defaultdict(list)
    for page_blocks in all_page_blocks:
        for b in page_blocks:
            t = b.text.strip()
            if t and len(t) < 120:  # headers/footers are short
                text_y_map[t].append(b.top)

    # A block is a header/footer if same text appears on enough pages at similar y
    def _is_hf_candidate(text: str, top: float) -> bool:
        ys = text_y_map.get(text, [])
        if len(ys) < threshold:
            return False
        matching = sum(1 for y in ys if abs(y - top) <= Y_TOLERANCE_PT)
        return matching >= threshold

    return [
        [b for b in page_blocks if not _is_hf_candidate(b.text.strip(), b.top)]
        for page_blocks in all_page_blocks
    ]


def extract_pdf_elements(
    pdf_path: str,
    image_dir: str,
    prefix: str = "img",
) -> tuple[list[list[TextBlock]], list[list[ImageBlock]], list[bool]]:
    """
    Extract TextBlocks and ImageBlocks from a PDF, one list per page.

    Returns:
        text_pages:   list[page] of list[TextBlock]  (header/footer stripped)
        image_pages:  list[page] of list[ImageBlock]
        multi_column: list[bool] — True if that page is detected as multi-column
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return [], [], []

    text_pages: list[list[TextBlock]] = []
    image_pages: list[list[ImageBlock]] = []
    multi_column_flags: list[bool] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_width = page.width or 595.0

            # ── Text extraction via .chars ───────────────────────────────
            chars = [
                c for c in (page.chars or [])
                if c.get("text") is not None
                and c.get("x0") is not None
                and c.get("top") is not None
                and c.get("size") is not None
            ]
            lines = _group_chars_into_lines(chars)
            raw_blocks = _lines_to_text_blocks(lines, page_num)

            is_mc = _detect_multi_column(raw_blocks, page_width)
            multi_column_flags.append(is_mc)
            ordered = _sort_blocks_reading_order(raw_blocks, is_mc, page_width)
            text_pages.append(ordered)

            # ── Image extraction ─────────────────────────────────────────
            page_images: list[ImageBlock] = []
            for img_obj in (page.images or []):
                try:
                    # pdfplumber image objects have stream data accessible via pypdf
                    # We'll extract via pypdf separately (pdfplumber wraps the same xref)
                    img_x0 = img_obj.get("x0", 0.0)
                    img_top = img_obj.get("top", 0.0)
                    img_x1 = img_obj.get("x1", img_x0)
                    img_bottom = img_obj.get("bottom", img_top)
                    # Placeholder — actual data extraction done below via pypdf
                    page_images.append(ImageBlock(
                        data=b"",
                        ext=".png",
                        x0=img_x0, top=img_top, x1=img_x1, bottom=img_bottom,
                        page_num=page_num,
                        rel_path="",
                        filename="",
                    ))
                except Exception as e:
                    logger.warning(f"Could not read image metadata on page {page_num}: {e}")

            image_pages.append(page_images)

    # ── Strip repeated headers/footers ──────────────────────────────────────
    text_pages = _strip_headers_footers(text_pages, len(text_pages))

    # ── Extract actual image bytes via pypdf (pdfplumber shares the same PDF) ─
    image_pages = _extract_image_bytes(pdf_path, image_pages, image_dir, prefix)

    return text_pages, image_pages, multi_column_flags


def _extract_image_bytes(
    pdf_path: str,
    image_pages: list[list[ImageBlock]],
    image_dir: str,
    prefix: str,
) -> list[list[ImageBlock]]:
    """Fill in image bytes + rel_path using pypdf, coordinating with the ImageBlock placeholders."""
    try:
        import pypdf
    except ImportError:
        logger.warning("pypdf not installed — images will be skipped.")
        return [[] for _ in image_pages]

    try:
        reader = pypdf.PdfReader(pdf_path)
    except Exception as e:
        logger.error(f"pypdf failed to open PDF for image extraction: {e}")
        return image_pages

    result: list[list[ImageBlock]] = []
    for page_idx, (page, placeholder_imgs) in enumerate(
        zip(reader.pages, image_pages)
    ):
        page_image_data: list[ImageBlock] = []
        try:
            pdf_imgs = page.images
        except Exception:
            pdf_imgs = []

        for i, img_obj in enumerate(pdf_imgs):
            # Match to placeholder by index (same order pdfplumber reported)
            placeholder = placeholder_imgs[i] if i < len(placeholder_imgs) else None

            try:
                ext = os.path.splitext(img_obj.name)[1].lower() if "." in img_obj.name else ".png"
                if not ext.startswith("."):
                    ext = f".{ext}"
                if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                    ext = ".png"

                filename = f"{prefix}_p{page_idx + 1}_{i + 1}_{uuid.uuid4().hex[:4]}{ext}"
                out_path = os.path.join(image_dir, filename)
                with open(out_path, "wb") as f:
                    f.write(img_obj.data)

                rel_path = f"images/{filename}"

                page_image_data.append(ImageBlock(
                    data=img_obj.data,
                    ext=ext,
                    x0=placeholder.x0 if placeholder else 0.0,
                    top=placeholder.top if placeholder else 0.0,
                    x1=placeholder.x1 if placeholder else 0.0,
                    bottom=placeholder.bottom if placeholder else 0.0,
                    page_num=page_idx + 1,
                    rel_path=rel_path,
                    filename=filename,
                ))
            except Exception as e:
                logger.warning(f"Failed to extract image {i} on page {page_idx + 1}: {e}")

        result.append(page_image_data)

    # Pad any remaining pages that pypdf didn't cover
    while len(result) < len(image_pages):
        result.append([])

    return result
