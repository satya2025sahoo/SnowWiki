"""
src/ingestion/backfill_clean_md_images.py
=========================================
Idempotent script to clean up Markdown image rendering issues in existing repository files:
1. Renames images on disk containing spaces or unsafe characters to sanitized filenames.
2. Updates Markdown image paths matching disk file renames.
3. Separates concatenated image tags with double linebreaks.
4. Fixes corrupted trailing brackets (e.g. `]]`).
"""

import os
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_images")

def sanitize_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    sanitized_name = re.sub(r'[^\w\-]+', '_', name).strip('_')
    return f"{sanitized_name}{ext}"

def backfill_markdown_and_images(upload_dir: str = "data/uploads"):
    """Scans upload_dir for markdown files and images to backfill clean paths."""
    for root, dirs, files in os.walk(upload_dir):
        if os.path.basename(root) == "images":
            continue
        
        md_files = [f for f in files if f.endswith(".md")]
        for md_file in md_files:
            md_path = os.path.join(root, md_file)
            img_dir = os.path.join(root, "images")
            
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 1. Map existing image files to sanitized names if needed
            renames = {}
            if os.path.exists(img_dir):
                for img_name in os.listdir(img_dir):
                    sanitized_img_name = sanitize_filename(img_name)
                    if img_name != sanitized_img_name:
                        old_img_path = os.path.join(img_dir, img_name)
                        new_img_path = os.path.join(img_dir, sanitized_img_name)
                        if not os.path.exists(new_img_path):
                            os.rename(old_img_path, new_img_path)
                            logger.info(f"Renamed image file: {img_name} -> {sanitized_img_name}")
                        renames[img_name] = sanitized_img_name

            # 2. Update markdown content references for renamed images
            updated_content = content
            for old_name, new_name in renames.items():
                updated_content = updated_content.replace(f"images/{old_name}", f"images/{new_name}")

            # 3. Clean corrupted brackets (e.g., `![alt](url]]`)
            updated_content = re.sub(r'(!\[[^\]\n]*\]\([^\)\n]+\)\]+)', lambda m: m.group(1).rstrip(']'), updated_content)

            # 4. Separate concatenated image tags onto independent paragraphs with \n\n
            pattern = re.compile(r'(!\[[^\]\n]*\]\([^\)\n]+\))\s*(?=\!\[)')
            while True:
                new_text = pattern.sub(r'\1\n\n', updated_content)
                if new_text == updated_content:
                    break
                updated_content = new_text

            # Write back if changed
            if updated_content != content:
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                logger.info(f"Updated markdown file: {md_path}")

if __name__ == "__main__":
    base_uploads = os.path.abspath("data/uploads")
    logger.info(f"Starting backfill in {base_uploads}")
    backfill_markdown_and_images(base_uploads)
