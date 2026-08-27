"""
src/ingestion/docx_utils.py
============================
DOCX → Markdown conversion utilities for the SnowWiki ingestion pipeline.

Separates DOCX-specific conversion logic from the core chunking algorithms
in chunking.py so each module stays focused on a single responsibility.

Public API
----------
convert_docx_to_markdown(file_path: str) -> str
"""

from __future__ import annotations

import re

from docx import Document


# ── Internal helpers ───────────────────────────────────────────────────────────

def _normalize_docx_markdown(md_text: str) -> str:
    """Enhance and fix Markdown generated from DOCX."""
    lines = md_text.splitlines()
    out_lines = []

    topic_pattern    = re.compile(r"^(Topic\s+\d+[:\-]?.*)$", re.IGNORECASE)
    numbered_pattern = re.compile(r"^(\d+\.\s+[A-Z][a-zA-Z0-9\s&]+)$")

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            out_lines.append("")
            continue

        if line_clean.startswith("**") and line_clean.endswith("**"):
            inner = line_clean.strip("*").strip()
            if topic_pattern.match(inner) or numbered_pattern.match(inner):
                out_lines.append(f"## {inner}")
                continue
            if len(inner) < 80:
                out_lines.append(f"### {inner}")
                continue

        if topic_pattern.match(line_clean):
            out_lines.append(f"## {line_clean}")
            continue

        if numbered_pattern.match(line_clean) and not line_clean.startswith("#"):
            out_lines.append(f"## {line_clean}")
            continue

        line = line.replace("\xa0", " ")
        out_lines.append(line)

    return "\n".join(out_lines)


def _fallback_convert_docx_to_markdown(file_path: str) -> str:
    """Pure-python DOCX → Markdown conversion used when mammoth is unavailable."""
    doc = Document(file_path)
    md_lines = []

    topic_pattern    = re.compile(r"^(Topic\s+\d+[:\-]?.*)$", re.IGNORECASE)
    numbered_pattern = re.compile(r"^(\d+\.\s+[A-Z][a-zA-Z0-9\s&]+)$")

    for p in doc.paragraphs:
        style_name = p.style.name if p.style else ""
        text = p.text.strip()
        if not text:
            continue

        is_bold_run = any(run.bold for run in p.runs)

        if style_name.startswith("Heading"):
            try:
                level = int(style_name.split()[-1])
                md_lines.append(f"{'#' * level} {text}\n")
            except ValueError:
                md_lines.append(f"# {text}\n")
        elif style_name == "Title":
            md_lines.append(f"# {text}\n")
        elif topic_pattern.match(text) or numbered_pattern.match(text):
            md_lines.append(f"## {text}\n")
        elif is_bold_run and len(text) < 80:
            md_lines.append(f"### {text}\n")
        elif style_name.startswith("List Bullet") or style_name == "List Paragraph":
            md_lines.append(f"- {text}")
        elif style_name.startswith("List Number"):
            md_lines.append(f"1. {text}")
        else:
            md_lines.append(text + "\n")

    for table in doc.tables:
        if not table.rows:
            continue
        header = table.rows[0]
        header_texts = [cell.text.strip().replace("\n", " ") for cell in header.cells]
        md_lines.append("\n| " + " | ".join(header_texts) + " |")
        md_lines.append("|" + "|".join(["---"] * len(header.cells)) + "|")
        for row in table.rows[1:]:
            row_texts = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            md_lines.append("| " + " | ".join(row_texts) + " |")
        md_lines.append("\n")

    return "\n".join(md_lines)


# ── Public API ─────────────────────────────────────────────────────────────────

def convert_docx_to_markdown(file_path: str) -> str:
    """
    Convert a DOCX file to structured Markdown using Mammoth.

    Translates Heading styles to Markdown headers (#, ##), bullets to lists,
    and applies semantic normalisation for pseudo-headings.
    Falls back to a pure-python implementation if mammoth is not installed.
    """
    try:
        import mammoth
        with open(file_path, "rb") as docx_file:
            result = mammoth.convert_to_markdown(docx_file)
            raw_md = result.value
            return _normalize_docx_markdown(raw_md)
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(
            "mammoth package not found. Using fallback DOCX to Markdown converter."
        )
        return _fallback_convert_docx_to_markdown(file_path)
