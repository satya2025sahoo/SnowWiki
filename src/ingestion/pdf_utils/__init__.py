"""
src/ingestion/pdf_utils/__init__.py
=====================================
PDF → Markdown conversion utilities for the SnowWiki ingestion pipeline.

Supersedes src/ingestion/structured_pdf_utils.py (deprecated — will be
removed next sprint after this package is validated in production).
"""

from src.ingestion.pdf_utils.converter import convert_pdf_to_markdown
from src.ingestion.pdf_utils.marker_converter import convert_pdf_with_marker

__all__ = [
    "convert_pdf_to_markdown",
    "convert_pdf_with_marker",
]
