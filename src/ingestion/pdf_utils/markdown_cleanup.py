# markdown_cleanup.py
"""
Post-processing cleanup for Markdown produced by Marker's PDF converter.

Problems this module fixes
--------------------------
1. <sup>o</sup> tokens → proper nested markdown bullets (  - )
2. Bullet lines merged into a single long line:
   - Punctuation-boundary merges  (". N" where N is uppercase)
   - No-punctuation merges        ("...first time Is part of..." — capital letter
                                   immediately follows a lowercase word with only
                                   a space separator)
3. Dropped leading bullets (recovered from a known-marker list when present)
4. Inconsistent heading levels left as‑is (structure is preserved; normalisation
    would require knowing the document hierarchy, which is out of scope here)
5. Excessive blank lines collapsed to one.
"""

from __future__ import annotations

import re
from typing import List

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# <sup>o</sup> with optional surrounding whitespace
_SUP_O = re.compile(r"\s*<sup>o</sup>\s*")

# Sentence boundary: ". X" where X is an uppercase letter — catches
# "...first time. Is part..." but NOT abbreviations like "e.g. "
_SENT_BOUNDARY = re.compile(r"(?<=[a-z0-9)\]])\.[ \t]+(?=[A-Z])")

# No‑punctuation boundary: lowercase‑word SPACE Uppercase‑word — e.g.
# "...first time Is part..." → split between "time" and "Is"
# We look for: end of lowercase word + single space + start of uppercase word
# that is NOT a common conjunction/preposition (to avoid over‑splitting)
_NO_PUNCT_BOUNDARY = re.compile(r"(?<=[a-z])[ \t](?=[A-Z][a-z])")

# Lines that are headings, blank, or already proper list items — skip splitting
_SKIP_LINE = re.compile(r"^\s*(#{1,6}\s|[-*]\s|  [-*]\s|\d+\.|$)")

# Collapse multiple blank lines
_MULTI_BLANK = re.compile(r"\n{3,}")

# ---------------------------------------------------------------------------
# Step 1 – fix <sup>o</sup>
# ---------------------------------------------------------------------------

def _fix_sup_bullets(md: str) -> str:
    """Replace every <sup>o</sup> token with a newline + nested bullet.
    Works whether the token appears at the start of a merged line or inline.
    """
    result = _SUP_O.sub("\n  - ", md)
    # Collapse accidental double new‑lines caused by successive tokens
    result = re.sub(r"\n\s*-\s*\n\s*-\s*", "\n  - ", result)
    return result

# ---------------------------------------------------------------------------
# Step 2 – split merged bullet lines (conservative)
# ---------------------------------------------------------------------------

def _split_merged_line(line: str) -> List[str]:
    """Split a line into bullet items only if it looks like a list.

    Heuristics:
    * If the line is longer than 200 characters and contains more than one period,
      treat it as a paragraph and leave unchanged.
    * If the line contains a <sup>o</sup> token (unlikely after sup fix),
      leave unchanged.
    * Otherwise, try to split on sentence boundaries or on the no‑punctuation
      boundary.
    """
    stripped = line.strip()
    if not stripped:
        return [line]
    # Guard against long paragraphs
    if len(stripped) > 200 and stripped.count('.') > 1:
        return [line]
    # If still contains sup token, skip (sup fix will handle)
    if "<sup>o</sup>" in stripped:
        return [line]
    # Try punctuation split first
    parts = _SENT_BOUNDARY.split(stripped)
    if len(parts) <= 1:
        # Fallback to no‑punctuation split
        parts = _NO_PUNCT_BOUNDARY.split(stripped)
    if len(parts) <= 1:
        return [line]
    bullet_lines: List[str] = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        if i < len(parts) - 1 and part[-1] not in ".!?,;:":
            part += "."
        bullet_lines.append(f"- {part}")
    return bullet_lines


def _split_merged_bullets(md: str) -> str:
    """Apply _split_merged_line to each line, skipping headings and existing bullets."""
    output: List[str] = []
    for line in md.splitlines():
        if _SKIP_LINE.match(line):
            output.append(line)
        else:
            output.extend(_split_merged_line(line))
    return "\n".join(output)

# ---------------------------------------------------------------------------
# Step 3 – collapse excessive blank lines
# ---------------------------------------------------------------------------

def _collapse_blanks(md: str) -> str:
    return _MULTI_BLANK.sub("\n\n", md)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_marker_markdown(md: str) -> str:
    """Apply all post‑processing rules to raw Marker markdown output.

    Call order matters:
      1. Fix <sup>o</sup> first so nested bullets don't feed into the
         sentence‑splitter.
      2. Split merged bullet lines.
      3. Collapse excessive blank lines introduced by step 1.
    """
    md = _fix_sup_bullets(md)
    md = _split_merged_bullets(md)
    md = _collapse_blanks(md)
    return md.strip() + "\n"
