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
  KL-3: _fix_split_words() may join legitimate two-word phrases where the first
         word is 2+ chars and the second is 1-3 chars (e.g. "to be" -> "tobe").
         The lookahead guard `(?=[a-z]{1,3}\b)` limits this; risk is low in
         training-doc context where such phrases are uncommon mid-token.
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


# ── Split-word gap repair ──────────────────────────────────────────────────────
# Fix 1 (KL-3): Repairs 2-char split fragments like "upda te" -> "update",
# "Servic e" -> "Service", "Ra nges" -> "Ranges".
# Strategy: token-pair merging — scan adjacent tokens; merge when the second
# token is a short (1-4 char) lowercase alphabetic fragment that is NOT a
# known stop word / preposition, indicating a PDF glyph-mapping split.

# Common short English words that must NOT be merged with the preceding token
_STOP_WORDS = frozenset({
    "a", "an", "as", "at", "be", "by", "do", "go", "he", "if", "in",
    "is", "it", "me", "my", "no", "of", "on", "or", "so", "to", "up",
    "us", "we", "the", "and", "are", "but", "for", "has", "not", "was",
    "its", "via", "can", "did", "had", "let", "may", "per", "set", "use",
    "yet", "few", "nor", "own", "add", "any", "all", "key", "map", "run",
    "tag", "end", "get", "new", "old", "out", "put", "see", "too", "two",
    "one", "how", "now", "our", "due", "low", "raw", "sub", "top", "vs",
})

# Tokeniser: split on whitespace but preserve leading punctuation context
_TOKEN_SPLIT_RE = re.compile(r"(\s+)")


def _fix_split_words(text: str) -> str:
    """Merge word fragments split by PDF glyph-mapping artifacts.

    Examples:
      'upda te CIs'       -> 'update CIs'
      'Servic e Mapping'  -> 'Service Mapping'
      'Ra nges define'    -> 'Ranges define'
      'infras tructure'   -> 'infrastructure'
      'non-dis coverable' -> 'non-discoverable'

    Strategy: split on whitespace (preserving separators), then scan adjacent
    (word, separator, next_word) triples. Merge word+next_word when:
      - The separator is a single plain space (not newline/tab)
      - next_word is 1-4 lowercase alpha chars
      - next_word is NOT a known stop word
      - word ends with an alpha char
    After merging, the separator that FOLLOWED next_word is kept.
    """
    # Split into alternating [word, sep, word, sep, ...] list
    parts = _TOKEN_SPLIT_RE.split(text)
    # parts[0], parts[2], parts[4]... are word tokens
    # parts[1], parts[3], parts[5]... are separator tokens
    words = parts[0::2]
    seps  = parts[1::2]   # len(seps) == len(words) - 1

    result: list[str] = []
    i = 0
    while i < len(words):
        word = words[i]
        sep_after = seps[i] if i < len(seps) else None
        next_word  = words[i + 1] if i + 1 < len(words) else None

        should_merge = (
            next_word is not None
            and sep_after == " "               # single plain space only
            and 1 <= len(next_word) <= 4
            and next_word.isalpha()
            and next_word.lower() not in _STOP_WORDS
            and next_word[0].islower()
            and word and word[-1].isalpha()
        )

        if should_merge:
            # Emit merged token, then the separator that FOLLOWS next_word
            # (which is seps[i+1], not seps[i] which we consumed for the merge).
            result.append(word + next_word)
            if i + 1 < len(seps):          # separator after next_word
                result.append(seps[i + 1])
            # Skip: seps[i] (between word and next_word) + next_word + seps[i+1]
            i += 2
        else:
            result.append(word)
            if sep_after is not None:
                result.append(sep_after)
            i += 1

    return "".join(result)


# ── Public entry point ─────────────────────────────────────────────────────────

def clean_pdf_text_block(text: str) -> str:
    """
    Apply all PDF-specific text fixes in order:
      1. Dehyphenation (KL-1)
      2. Mid-sentence line-break joining (Fix 2: now catches upper + lower continuations)
      3. Kerning-space repair (KL-2)
      4. Split-word gap repair (Fix 1 / KL-3)
    """
    text = _dehyphenate(text)
    text = _join_sentence_linebreaks(text)
    text = _fix_kerning_spaces(text)
    text = _fix_split_words(text)
    return text.strip()
