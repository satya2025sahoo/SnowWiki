# markdown_cleanup.py
"""
Post-processing cleanup for Markdown produced by Marker's PDF converter.

Safe Normalization:
-------------------
1. <sup>o</sup> and `- o ` tokens → proper nested markdown bullets (  - )
2. Collapse excessive blank lines.
3. Preserve Marker's native layout (headings, prose blocks, tables, callouts)
   without forcibly splitting sentences or capitalized phrases into bullet points.
"""

from __future__ import annotations

import re
from typing import List

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# <sup>o</sup> with optional surrounding whitespace
_SUP_O = re.compile(r"\s*<sup>o</sup>\s*")

# OCR sub-bullets like "- o " or "* o "
_DASH_O = re.compile(r"(?m)^([ \t]*[-*])\s+o\s+")

# Collapse multiple blank lines
_MULTI_BLANK = re.compile(r"\n{3,}")


# ---------------------------------------------------------------------------
# Step 1 – fix sub-bullet tokens
# ---------------------------------------------------------------------------

def _fix_sup_bullets(md: str) -> str:
    """Replace <sup>o</sup> or '- o ' tokens with proper nested bullets.
    Works whether the token appears at the start of a line or inline.
    """
    result = _SUP_O.sub("\n  - ", md)
    result = _DASH_O.sub(r"  \1 ", result)
    result = re.sub(r"\n\s*-\s*\n\s*-\s*", "\n  - ", result)
    return result


# ---------------------------------------------------------------------------
# Step 2 – collapse excessive blank lines
# ---------------------------------------------------------------------------

def _collapse_blanks(md: str) -> str:
    return _MULTI_BLANK.sub("\n\n", md)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_marker_markdown(md: str, apply_structurer: bool = False) -> str:
    """Apply post‑processing rules to raw Marker markdown output.

    Marker (especially in balanced mode) generates high-fidelity markdown with
    accurate blocks, headings, lists, and tables. We only perform safe
    token cleanup (fixing <sup>o</sup> sub-bullets and blank lines) to avoid
    destroying prose blocks or turning capitalized words into unwanted bullets.
    """
    md = _fix_sup_bullets(md)
    md = _collapse_blanks(md)

    if apply_structurer:
        try:
            from .structurer import structure_markdown
        except ImportError:
            try:
                from ingestion.pdf_utils.structurer import structure_markdown
            except ImportError:
                from src.ingestion.pdf_utils.structurer import structure_markdown
        md = structure_markdown(md)

    return md.strip() + "\n"

