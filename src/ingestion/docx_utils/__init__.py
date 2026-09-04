"""
src/ingestion/docx_utils/__init__.py
======================================
DOCX → Markdown conversion utilities for the SnowWiki ingestion pipeline.

Separates DOCX-specific conversion logic from the core chunking algorithms
in chunking.py so each module stays focused on a single responsibility.
"""

from src.ingestion.docx_utils.converter import convert_docx_to_markdown
from src.ingestion.docx_utils.normalization import _normalize_docx_markdown
from src.ingestion.docx_utils.heuristics import _is_servicenow_code, _is_valid_pseudo_heading
from src.ingestion.docx_utils.tables import _convert_table_to_markdown_or_html, _sanitize_table_cells
from src.ingestion.docx_utils.extraction import _extract_paragraph_markdown

__all__ = [
    "convert_docx_to_markdown",
    "_normalize_docx_markdown",
    "_is_servicenow_code",
    "_is_valid_pseudo_heading",
    "_convert_table_to_markdown_or_html",
    "_sanitize_table_cells",
    "_extract_paragraph_markdown",
]
