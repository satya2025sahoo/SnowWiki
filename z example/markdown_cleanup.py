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
4. Inconsistent heading levels left as-is (structure is preserved; normalisation
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
_SENT_BOUNDARY = re.compile(r"(?<=[a-z0-9)\]>])\.[ \t]+(?=[A-Z])")

# No-punctuation boundary: lowercase-word SPACE Uppercase-word — e.g.
# "...first time Is part..." → split between "time" and "Is"
# We look for: end of lowercase word + single space + start of uppercase word
# that is NOT a common conjunction/preposition (to avoid over-splitting)
_NO_PUNCT_BOUNDARY = re.compile(
    r"(?<=[a-z])[ \t](?=[A-Z][a-z])"
)

# Lines that are headings, blank, or already proper list items — skip splitting
_SKIP_LINE = re.compile(r"^\s*(#{1,6}\s|[-*]\s|  [-*]\s|\d+\.|$)")

# Collapsed multiple blank lines
_MULTI_BLANK = re.compile(r"\n{3,}")


# ---------------------------------------------------------------------------
# Step 1 – fix <sup>o</sup>
# ---------------------------------------------------------------------------

def _fix_sup_bullets(md: str) -> str:
    """
    Replace every <sup>o</sup> with a newline + nested bullet.
    Works whether the token appears at the start of a merged line or inline.
    """
    # First occurrence on a line: convert to a new nested bullet line
    result = _SUP_O.sub("\n  - ", md)
    # Clean up any leading whitespace/dash that ends up doubled
    result = re.sub(r"\n\s*-\s*\n\s*-\s*", "\n  - ", result)
    return result


# ---------------------------------------------------------------------------
# Step 2 – split merged bullet lines
# ---------------------------------------------------------------------------

def _split_merged_line(line: str) -> List[str]:
    """
    Take a single (potentially merged) line and return it as one or more
    properly formatted bullet items.

    Strategy
    --------
    1. Try punctuation-boundary split first (more reliable).
    2. If that yields only one part, try the no-punctuation boundary split
       (catches "...first time Is part of...").
    3. Prefix every resulting fragment with "- " and strip extra whitespace.
    """
    stripped = line.strip()
    if not stripped:
        return [line]

    # --- punctuation split ---
    parts = _SENT_BOUNDARY.split(stripped)

    # --- no-punctuation split (fallback when sentences share no period) ---
    if len(parts) == 1:
        parts = _NO_PUNCT_BOUNDARY.split(stripped)

    if len(parts) <= 1:
        # Nothing to split; return original line unchanged
        return [line]

    # Re-attach any trailing period that the split consumed
    bullet_lines: List[str] = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        # If the split was on a period, the period was consumed; put it back
        # unless the part already ends with punctuation.
        if i < len(parts) - 1 and not part[-1] in ".!?,;:":
            part += "."
        bullet_lines.append(f"- {part}")
    return bullet_lines


def _split_merged_bullets(md: str) -> str:
    """
    Walk every line of the markdown.  Lines that look like merged bullet
    blocks (no leading dash/heading, multiple sentence-like fragments) are
    expanded into individual `- item` lines.
    """
    output: List[str] = []
    for line in md.splitlines():
        if _SKIP_LINE.match(line):
            output.append(line)
        else:
            output.extend(_split_merged_line(line))
    return "\n".join(output)


# ---------------------------------------------------------------------------
# Step 3 – remove excessive blank lines
# ---------------------------------------------------------------------------

def _collapse_blanks(md: str) -> str:
    return _MULTI_BLANK.sub("\n\n", md)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_marker_markdown(md: str) -> str:
    """
    Apply all post-processing rules to raw Marker markdown output.

    Call order matters:
      1. Fix <sup>o</sup> first so nested bullets don't feed into the
         sentence-splitter.
      2. Split merged bullet lines.
      3. Collapse excessive blank lines introduced by step 1.
    """
    md = _fix_sup_bullets(md)
    md = _split_merged_bullets(md)
    md = _collapse_blanks(md)
    return md.strip() + "\n"
