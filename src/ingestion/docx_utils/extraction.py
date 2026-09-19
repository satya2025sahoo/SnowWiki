import os
import uuid
import logging
from typing import Any

logger = logging.getLogger(__name__)

def _extract_paragraph_markdown(
    p: Any,
    branch_name: str = "default",
    image_dir: str | None = None,
    image_describer: Any = None,
    prefix: str = "doc"
) -> tuple[str, bool]:
    """
    Extracts text from a python-docx Paragraph element with:
    - Word hyperlink XML extraction: [Anchor](URL)
    - Inline formatting: bold (**), italic (*), code (`)
    - Embedded image drawing extraction to branch image directory
    Returns (paragraph_text, is_fully_bold).
    """
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    parts = []
    has_text = False
    all_runs_bold = True
    run_count = 0

    for child in p._element:
        tag = child.tag
        if tag.endswith("hyperlink"):
            # Hyperlink element: <w:hyperlink r:id="...">
            r_id = child.attrib.get(f"{{{r_ns}}}id")
            url = ""
            if r_id and hasattr(p, "part") and r_id in p.part.rels:
                url = p.part.rels[r_id].target_ref

            link_text = "".join(node.text for node in child.xpath(".//w:t") if node.text).strip()
            if link_text:
                has_text = True
                run_count += 1
                all_runs_bold = False
                if url:
                    parts.append(f"[{link_text}]({url})")
                else:
                    parts.append(link_text)

        elif tag.endswith("r"):
            # Check for embedded drawings/images
            blip_ids = child.xpath(".//a:blip/@r:embed")
            if blip_ids and image_dir:
                for b_id in blip_ids:
                    if hasattr(p, "part") and b_id in p.part.rels:
                        img_part = p.part.rels[b_id].target_part
                        ext = ".png"
                        if "jpeg" in img_part.content_type:
                            ext = ".jpg"
                        elif "gif" in img_part.content_type:
                            ext = ".gif"
                        filename = f"{prefix}_fb_{uuid.uuid4().hex[:6]}{ext}"
                        out_path = os.path.join(image_dir, filename)
                        rel_path = f"images/{filename}"
                        try:
                            with open(out_path, "wb") as f:
                                f.write(img_part.blob)
                        except Exception as e:
                            logger.warning(f"Failed to write image {filename}: {e}")

                        # Image description via API is disabled (too slow — skipped for now)
                        # desc = None
                        # if image_describer:
                        #     try:
                        #         desc = image_describer.describe_from_path(out_path)
                        #     except Exception as e:
                        #         logger.warning(f"Fallback image describe error: {e}")
                        # if not desc or "unavailable" in desc.lower() or "error" in desc.lower() or not desc.strip():
                        #     desc = f"Image: {filename} - Description Unavailable"
                        desc = f"Image: {filename}"
                        parts.append(f"\n\n![{desc}]({rel_path})\n\n")

            # Check text runs
            text = "".join(node.text for node in child.xpath(".//w:t") if node.text)
            if text:
                has_text = True
                run_count += 1
                is_bold = bool(child.xpath("./w:rPr/w:b[not(@w:val='0' or @w:val='false')]"))
                is_italic = bool(child.xpath("./w:rPr/w:i[not(@w:val='0' or @w:val='false')]"))
                is_code = bool(child.xpath("./w:rPr/w:rFonts[@w:ascii='Consolas' or @w:ascii='Courier New']"))

                if not is_bold:
                    all_runs_bold = False

                formatted = text
                if is_code:
                    formatted = f"`{formatted}`"
                elif is_bold and is_italic:
                    formatted = f"***{formatted}***"
                elif is_bold:
                    formatted = f"**{formatted}**"
                elif is_italic:
                    formatted = f"*{formatted}*"

                parts.append(formatted)

    full_text = "".join(parts).strip()
    is_bold_para = has_text and all_runs_bold and run_count > 0
    return full_text, is_bold_para
