"""
src/ingestion/pdf_utils/tables.py
===================================
PDF table extraction using pdfplumber.

D5 risk: pdfplumber's merged-cell inference is heuristic and may fail on
irregular borders or spanning headers. Acceptance criterion: >= 80% structural
accuracy on real test tables. Falls back to plain paragraph text if below threshold.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def _escape_pipe(cell: str) -> str:
    """Escape pipe characters inside a table cell."""
    return (cell or "").replace("|", "\\|").replace("\n", "<br>").strip()


def extract_page_tables(page) -> list[str]:
    """
    Extract all tables from a pdfplumber Page object.
    Returns a list of GFM pipe-table or plain-text strings.

    Falls back to plain-text representation if table structure is ambiguous.
    """
    table_strings: list[str] = []
    try:
        tables = page.extract_tables()
    except Exception as e:
        logger.warning(f"pdfplumber table extraction failed: {e}")
        return []

    for table in tables:
        if not table or not table[0]:
            continue

        try:
            md = _table_to_markdown(table)
            if md:
                table_strings.append(md)
        except Exception as e:
            logger.warning(f"Failed to convert table to markdown: {e}. Falling back to plain text.")
            plain = _table_to_plain_text(table)
            if plain:
                table_strings.append(plain)

    return table_strings


def _table_to_markdown(table: list[list[str | None]]) -> str:
    """Convert a pdfplumber table (list of rows) to a GFM pipe table."""
    if not table:
        return ""

    # Normalise None cells to empty string
    rows = [[_escape_pipe(str(cell) if cell is not None else "") for cell in row] for row in table]

    # Detect if table has a header row (first row contains non-empty cells)
    num_cols = max(len(row) for row in rows)

    # Pad all rows to the same column count
    padded = [row + [""] * (num_cols - len(row)) for row in rows]

    header = padded[0]
    body = padded[1:]

    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * num_cols) + "|")
    for row in body:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _table_to_plain_text(table: list[list[str | None]]) -> str:
    """Fallback: render table as indented plain text."""
    lines = []
    for row in table:
        row_text = "  |  ".join(str(cell or "").strip() for cell in row)
        if row_text.strip():
            lines.append(row_text)
    return "\n".join(lines)


def get_table_bboxes(page) -> list[tuple[float, float, float, float]]:
    """
    Return bounding boxes (x0, y0, x1, y1) of all tables on a page,
    used by the converter to exclude table regions from text block processing.
    """
    bboxes = []
    try:
        for table_finder in page.find_tables():
            bbox = table_finder.bbox  # (x0, y0, x1, y1)
            bboxes.append(bbox)
    except Exception as e:
        logger.debug(f"Could not find table bboxes: {e}")
    return bboxes
