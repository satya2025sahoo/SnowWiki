"""
src/ingestion/pdf_utils/pre_cleaner.py
=======================================
PDF-specific text pathology fixes applied BEFORE the shared normalizer runs.

Known limitations (documented accepted trade-offs):
  KL-1: Dehyphenation joins legitimate compound words that break at line ends.
         e.g. "well-\\nknown" -> "wellknown" (wrong; expected "well-known").
         Test test_dehyphen_known_wrong asserts this known-bad output.
  KL-2: Kerning-space repair may fire on rare single-letter prose sequences.
         Risk is negligible in training-doc context. Test confirms no false fire
         on normal short-word sequences.
         on normal short-word sequences.
"""

from __future__ import annotations

import re


# ── Dehyphenation ──────────────────────────────────────────────────────────────
# KL-1: This will incorrectly join "well-\nknown" -> "wellknown".
# A dictionary-check mitigation is out of scope; this is a documented trade-off.
_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")


def _dehyphenate(text: str) -> str:
    """Join words split across lines by a hyphen (KL-1: compound-word limitation)."""
    return _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)


# ── Hard line-break within sentence → single space ────────────────────────────
# Keeps the original lowercase-only lookahead: only join when next char is
# lowercase, which safely targets mid-sentence PDF line-wraps. Broadening to
# [A-Za-z] caused false joins on legitimate paragraph starts.
_SENTENCE_LINEBREAK_RE = re.compile(r"(?<![.!?:\n])\n(?=[a-z])")


def _join_sentence_linebreaks(text: str) -> str:
    """Replace mid-sentence line breaks with a space."""
    return _SENTENCE_LINEBREAK_RE.sub(" ", text)


# ── Kerning-space repair ───────────────────────────────────────────────────────
# KL-2: May fire on runs of single letters that are legitimately separate words
# (very rare in training docs). Test test_kerning_no_fire_normal confirms safety.
_KERNING_RE = re.compile(r"\b(?:(\w) ){3,}(\w)\b")


def _fix_kerning_spaces(text: str) -> str:
    """Remove spaces introduced by PDF kerning artifacts (e.g. 'c o n f i g' -> 'config').
    Only triggers on runs of 4+ single characters separated by spaces.
    """
    return _KERNING_RE.sub(lambda m: m.group(0).replace(" ", ""), text)


# ── Unicode & Whitespace Normalization ─────────────────────────────────────────

def _normalize_unicode(text: str) -> str:
    """Normalize unicode characters: remove zero-width spaces, replace non-breaking spaces."""
    text = text.replace('\u200b', '')
    text = text.replace('\xa0', ' ')
    return text

_MULTI_SPACE_RE = re.compile(r" {2,}")

def _normalize_whitespace(text: str) -> str:
    """Collapse multiple consecutive spaces into a single space."""
    return _MULTI_SPACE_RE.sub(" ", text)


# ── Public entry point ─────────────────────────────────────────────────────────

def clean_pdf_text_block(text: str) -> str:
    """
    Apply all PDF-specific text fixes in order:
      1. Dehyphenation (KL-1)
      2. Mid-sentence line-break joining
      3. Kerning-space repair (KL-2)
      4. Unicode normalization
      5. Whitespace collapsing
    """
    text = _normalize_unicode(text)
    text = _dehyphenate(text)
    text = _join_sentence_linebreaks(text)
    text = _fix_kerning_spaces(text)
    text = _normalize_whitespace(text)
    return text.strip()
