import re

def _is_servicenow_code(text: str) -> bool:
    """
    Weighted pattern-matching heuristic for ServiceNow-specific script detection.
    Require at least 1 High Confidence Trigger OR 2 Syntax Multi-Matches.
    """
    high_confidence = [
        r"g_form\.", r"gs\.", r"new GlideRecord", r"GlideAggregate",
        r"current\.setValue", r"action\.setRedirectURL", r"JSON\.parse"
    ]
    multi_match = [
        r"function\s+\w+\s*\(", r"\}\s*;", r"return\s+false;"
    ]

    hc_matches = sum(1 for p in high_confidence if re.search(p, text))
    if hc_matches >= 1:
        return True

    mm_matches = sum(1 for p in multi_match if re.search(p, text))
    if mm_matches >= 2:
        return True

    return False


# ── Heading & Pseudo-Heading Validation Heuristics ────────────────────────────

_REJECT_HEADING_PREFIXES = (
    "note", "notice", "warning", "danger", "caution", "important",
    "tip", "hint", "figure", "table", "step", "example", "image"
)


def _is_rejected_heading(text: str) -> bool:
    """Check if text starts with callout or caption words that should never be headings."""
    t = text.strip().lower()
    for prefix in _REJECT_HEADING_PREFIXES:
        if re.match(rf"^{prefix}(?:\s+\d+)?[:\s\-]", t) or t == prefix or t == f"{prefix}:":
            return True
    return False


def _is_valid_pseudo_heading(inner: str) -> bool:
    """
    Validate whether a bold text or standalone line qualifies as a Markdown heading.
    Prevents false positives on notes, captions, steps, and sentences ending in punctuation.
    """
    t = inner.strip()
    if not t or len(t) > 80:
        return False
    if t[-1] in ".,:;?!":
        return False
    if _is_rejected_heading(t):
        return False
    words = [w for w in t.split() if w.isalpha()]
    if not words or len(words) > 10:
        return False
    minor = {"and", "or", "of", "to", "in", "for", "with", "a", "an", "the", "by", "on", "at", "from", "is", "are"}
    sig = [w for w in words if w.lower() not in minor]
    if not sig:
        return False
    cap = sum(1 for w in sig if w[0].isupper())
    # Require at least 65% capitalized significant words or entire string uppercase
    if (cap / len(sig)) >= 0.65 or t.isupper():
        return True
    return False


def _is_plain_heading(text: str, prev_blank: bool, next_blank: bool) -> bool:
    """
    Detect standalone lines that look like section headings even without bold/style.
    Requires both surrounding blank lines for context safety.
    """
    t = text.strip()
    if not (prev_blank and next_blank):
        return False
    if not t or len(t) > 80:
        return False
    if len(t.split()) > 8:
        return False
    if t[-1] in ".,:;?":          # sentences end with punctuation; headings don't
        return False
    if t[0] in "-*#>|`":          # already formatted
        return False
    if t == t.lower():             # all-lowercase = prose
        return False
    if _is_rejected_heading(t):
        return False
    return True
