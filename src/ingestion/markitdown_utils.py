"""
src/ingestion/markitdown_utils.py
=================================
Unified Document to Markdown conversion using Microsoft MarkItDown.
Supports DOCX and PDF formats. Extracts images, generates descriptions, 
and injects markdown image tags.
"""

from __future__ import annotations

import os
import re
import uuid
import logging
import zipfile

# If PDF processing requires it:
try:
    from pdf2image import convert_from_path
except ImportError:
    pass

from src.ingestion.image_describer import ImageDescriberAgent
from src.ingestion.docx_utils import _is_servicenow_code, _sanitize_table_cells
from src.ingestion.core import get_branch_image_dir

logger = logging.getLogger(__name__)


def extract_images_from_docx(docx_path: str, output_dir: str, prefix: str = "img") -> list[str]:
    """Extract embedded images from a DOCX file directly from the zip archive."""
    image_paths = []
    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            for item in zf.namelist():
                if item.startswith("word/media/"):
                    ext = os.path.splitext(item)[1].lower()
                    if ext in [".png", ".jpeg", ".jpg", ".gif", ".webp"]:
                        # Extract and save
                        img_data = zf.read(item)
                        filename = f"{prefix}_{uuid.uuid4().hex[:6]}{ext}"
                        out_path = os.path.join(output_dir, filename)
                        with open(out_path, "wb") as f:
                            f.write(img_data)
                        image_paths.append(out_path)
    except Exception as e:
        logger.error(f"Error extracting images from DOCX: {e}")
    return image_paths


def convert_document_to_markdown_with_images(
    file_path: str, branch_name: str, file_ext: str
) -> str:
    """
    Convert DOCX or PDF to Markdown using MarkItDown.
    Extract images, describe them, and append/inject tags.
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        logger.error("markitdown not installed.")
        return ""

    md = MarkItDown()
    try:
        result = md.convert(file_path)
        raw_md = result.text_content
    except Exception as e:
        logger.error(f"MarkItDown conversion failed for {file_path}: {e}")
        return ""

    # Image Extraction
    image_dir = get_branch_image_dir(branch_name)
    extracted_images = []
    prefix = os.path.splitext(os.path.basename(file_path))[0]

    if file_ext == ".docx":
        extracted_images = extract_images_from_docx(file_path, image_dir, prefix=prefix)
    elif file_ext == ".pdf":
        try:
            # We'll just append page screenshots for PDF if python-fitz/PyMuPDF or pdf2image is used.
            # MarkItDown natively converts PDFs to markdown. We extract page images if pdf2image is available.
            images = convert_from_path(file_path)
            for i, img in enumerate(images):
                img_path = os.path.join(image_dir, f"{prefix}_page_{i+1}.png")
                img.save(img_path, "PNG")
                extracted_images.append(img_path)
        except Exception as e:
            logger.warning(f"Failed to extract PDF images (is poppler/pdf2image installed?): {e}")

    # Describe Images
    image_describer = ImageDescriberAgent()
    image_markdown_tags = []
    
    for img_path in extracted_images:
        desc = image_describer.describe_from_path(img_path)
        # We need a relative path from the app root for Streamlit or just an absolute path.
        # It's safest to store absolute paths in Markdown or standard relative to project root.
        tag = f"![{desc}]({img_path})"
        image_markdown_tags.append(tag)

    # Normalize MarkItDown output (Tables & Code)
    normalized_md = _normalize_markitdown_output(raw_md)

    # Append image tags at the bottom for now if we can't inline them perfectly. 
    # For DOCX, MarkItDown might omit image tags completely, so appending them gives context.
    # Future enhancement: Attempt to replace placeholder tags if MarkItDown emits them.
    if image_markdown_tags:
        normalized_md += "\n\n### Document Images\n\n"
        normalized_md += "\n\n".join(image_markdown_tags)

    return normalized_md


def _normalize_markitdown_output(md_text: str) -> str:
    """Apply ServiceNow heuristics and fix tables to MarkItDown output."""
    # Fix tables
    md_text = _sanitize_table_cells(md_text)

    lines = md_text.splitlines()
    out_lines = []

    topic_pattern    = re.compile(r"^(Topic\s+\d+[:\-]?.*)$", re.IGNORECASE)
    numbered_pattern = re.compile(r"^(\d+\.\s+[A-Z][a-zA-Z0-9\s&]+)$")

    in_code_block = False

    for line in lines:
        line_clean = line.strip()
        
        if line_clean.startswith("```"):
            in_code_block = not in_code_block
            out_lines.append(line)
            continue
            
        if in_code_block:
            out_lines.append(line)
            continue

        if not line_clean:
            out_lines.append("")
            continue

        # Normalise Headers
        if line_clean.startswith("**") and line_clean.endswith("**"):
            inner = line_clean.strip("*").strip()
            if topic_pattern.match(inner) or numbered_pattern.match(inner):
                out_lines.append(f"### {inner}")
                continue

        out_lines.append(line)

    final_text = "\n".join(out_lines)
    
    # Wrap ServiceNow code
    paras = final_text.split("\n\n")
    for i, p in enumerate(paras):
        if not p.strip().startswith("```") and _is_servicenow_code(p):
            paras[i] = f"```javascript\n{p.strip()}\n```"
            
    return "\n\n".join(paras)
