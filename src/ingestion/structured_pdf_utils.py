"""
src/ingestion/structured_pdf_utils.py
=====================================
Pure Python PDF to Markdown converter using font-size heuristics.
Extracts embedded images via pypdf and structures text via pdfminer.six.
"""

from __future__ import annotations

import os
import re
import uuid
import logging

from src.ingestion.image_describer import ImageDescriberAgent
from src.ingestion.core import get_branch_image_dir

logger = logging.getLogger(__name__)

def extract_images_from_pdf(pdf_path: str, output_dir: str, prefix: str = "img") -> list[str]:
    """Extract all embedded images from a PDF using pypdf (pure Python)."""
    image_paths = []
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        for page_idx, page in enumerate(reader.pages):
            for img_idx, img_obj in enumerate(page.images):
                ext = os.path.splitext(img_obj.name)[1].lower() if "." in img_obj.name else ".png"
                if not ext.startswith("."):
                    ext = f".{ext}"
                filename = f"{prefix}_p{page_idx+1}_{img_idx+1}_{uuid.uuid4().hex[:4]}{ext}"
                out_path = os.path.join(output_dir, filename)
                with open(out_path, "wb") as f:
                    f.write(img_obj.data)
                image_paths.append(out_path)
    except Exception as e:
        logger.error(f"Error extracting images from PDF {pdf_path}: {e}")
    return image_paths

def convert_pdf_to_structured_markdown(file_path: str, branch_name: str = "default") -> str:
    """
    Parse PDF into structured markdown using pdfminer.six for text and pypdf for images.
    Applies font-size heuristics to detect #, ##, ### headers.
    """
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextContainer, LTChar, LTTextLineHorizontal
    except ImportError:
        logger.error("pdfminer.six not installed. Cannot extract structured PDF.")
        return ""

    md_lines = []
    
    # Heuristics Patterns
    topic_pattern = re.compile(r"^(Topic\s+\d+[:\-]?.*)$", re.IGNORECASE)
    chapter_pattern = re.compile(r"^(Chapter\s+\d+[:\-]?.*)$", re.IGNORECASE)
    numbered_pattern = re.compile(r"^(\d+\.\s+[A-Z][a-zA-Z0-9\s&]+)$")
    subnum_pattern = re.compile(r"^(\d+\.\d+\s+[A-Z].*)$")

    try:
        for page_layout in extract_pages(file_path):
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    text = element.get_text().strip()
                    if not text:
                        continue
                    
                    # Compute average font size
                    sizes = []
                    is_bold = False
                    if hasattr(element, "_objs"):
                        for line in element._objs:
                            if isinstance(line, LTTextLineHorizontal):
                                for char in line._objs:
                                    if isinstance(char, LTChar):
                                        sizes.append(char.size)
                                        if "bold" in char.fontname.lower():
                                            is_bold = True
                    
                    avg_size = sum(sizes) / len(sizes) if sizes else 10.0
                    
                    # Apply heuristics
                    clean_text = text.replace("\n", " ")
                    
                    if avg_size >= 18 or (text.isupper() and len(text) > 4 and len(text) < 60):
                        md_lines.append(f"\n# {clean_text}\n")
                    elif 14 <= avg_size < 18 or topic_pattern.match(clean_text) or chapter_pattern.match(clean_text):
                        md_lines.append(f"\n## {clean_text}\n")
                    elif 12 <= avg_size < 14 or numbered_pattern.match(clean_text) or subnum_pattern.match(clean_text) or (is_bold and len(clean_text) < 80):
                        md_lines.append(f"\n### {clean_text}\n")
                    elif clean_text.startswith("•") or clean_text.startswith("-") or clean_text.startswith("*"):
                        md_lines.append(f"{clean_text}")
                    else:
                        from src.ingestion.docx_utils import _is_servicenow_code
                        if _is_servicenow_code(clean_text):
                            md_lines.append(f"\n```javascript\n{clean_text}\n```\n")
                        else:
                            md_lines.append(f"{clean_text}\n")
    except Exception as e:
        logger.error(f"Error parsing PDF layout: {e}")
        return ""

    raw_md = "\n".join(md_lines)

    # 2. Extract Images via pypdf
    image_dir = get_branch_image_dir(branch_name)
    prefix = os.path.splitext(os.path.basename(file_path))[0]
    extracted_images = extract_images_from_pdf(file_path, image_dir, prefix=prefix)
    
    # 3. Append Images (description API disabled — too slow, skipped for now)
    if extracted_images:
        # image_describer = ImageDescriberAgent()  # disabled
        image_markdown_tags = []
        for img_path in extracted_images:
            filename = os.path.basename(img_path)
            # API call skipped — just use filename as placeholder
            tag = f"![Image: {filename}]({img_path})"
            image_markdown_tags.append(tag)
        
        raw_md += "\n\n### Document Images\n\n"
        raw_md += "\n\n".join(image_markdown_tags)

    return raw_md
