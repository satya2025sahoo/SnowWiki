"""
src/ingestion/docx_utils.py
============================
DOCX → Markdown conversion utilities for the SnowWiki ingestion pipeline.

Separates DOCX-specific conversion logic from the core chunking algorithms
in chunking.py so each module stays focused on a single responsibility.

Public API
----------
convert_docx_to_markdown(file_path: str, branch_name: str = "default") -> str
"""

from __future__ import annotations

import os
import re
import html
import uuid
import logging
from typing import Any

from docx import Document

logger = logging.getLogger(__name__)


# ── Internal helpers ───────────────────────────────────────────────────────────

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


def _split_inline_bullets(line: str) -> list[str]:
    """
    Mammoth sometimes collapses consecutive list items into a single line like:
      '- Item one. - Item two. - Item three.'
    This function splits them back into individual bullet lines.
    """
    stripped = line.strip()
    if not stripped.startswith("- "):
        return [line]
    content = stripped[2:]
    if " - " not in content:
        return [line]
    parts = re.split(r"\s+-\s+", content)
    return [f"- {p.strip()}" for p in parts if p.strip()]


def _sanitize_table_cells(md_text: str) -> str:
    """
    Multi-Line Table Cell Sanitization: Replace internal \\n in table cells with <br>.
    Mammoth output creates tables where cell contents might contain newlines.
    """
    lines = md_text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith('|') and line.strip().endswith('|'):
            lines[i] = line.replace("\\n", "<br>")
    return "\n".join(lines)


# ── Callout / Admonition Normalization Helpers ────────────────────────────────

_ADMONITION_MAP = {
    "note": "NOTE",
    "notice": "NOTE",
    "warning": "WARNING",
    "danger": "WARNING",
    "important": "IMPORTANT",
    "tip": "TIP",
    "hint": "TIP",
    "caution": "CAUTION",
}

_ADMONITION_RE = re.compile(
    r"^\*{0,2}(Note|Notice|Warning|Danger|Important|Tip|Hint|Caution)\*{0,2}[:\-]?(?:\*\*)?\s*(.*)$",
    re.IGNORECASE
)


def _format_admonition(tag: str, first_line_content: str, subsequent_lines: list[str] | None = None) -> list[str]:
    """
    Format an admonition into GitHub-style alert blockquotes.
    Ensures every subsequent line is prefixed with '> ' (Refinement 1).
    """
    lines = [f"> [!{tag}]"]
    if first_line_content.strip():
        lines.append(f"> {first_line_content.strip()}")
    if subsequent_lines:
        for sub in subsequent_lines:
            s = sub.strip()
            if not s:
                lines.append(">")
            else:
                lines.append(f"> {s}")
    return lines


def _unwrap_single_cell_pipe_tables(text: str) -> str:
    """
    Detect single-cell 1x1 pipe tables emitted by Mammoth:
      | Note: Make sure to check ACLs. |
      | --- |
    and unwrap them into clean blockquotes or GitHub-style admonitions.
    """
    pattern = re.compile(
        r"^\|\s*([^|\n]+?)\s*\|\s*\n\|\s*[-:]+\s*\|\s*$",
        re.MULTILINE
    )

    def _repl(match):
        content = match.group(1).strip()
        adm = _ADMONITION_RE.match(content)
        if adm:
            tag = _ADMONITION_MAP.get(adm.group(1).lower(), "NOTE")
            rest = adm.group(2).strip()
            lines = _format_admonition(tag, rest)
            return "\n".join(lines)
        return f"> {content}"

    return pattern.sub(_repl, text)


# ── Normalization Engine ──────────────────────────────────────────────────────

class TwoPassDocumentNormalizer:
    """
    Two-pass Markdown normalizer for Mammoth-generated DOCX output.

    Pass 1 — Analyse: Reads every line and builds a document blueprint:
      - Collects all numbered sequences (e.g. '1.', '1.2', '1.2.1').
      - Flags sequences that have children (→ these become headings).
      - Detects bullet symbol frequencies for consistent indent rules.

    Pass 2 — Transform: Uses the blueprint to format each line with full context:
      - Numbered sequences with children → Markdown heading (## / ###).
      - Numbered sequences without children in a run → indented list item.
      - Solid bullets (•●) → `- item`.
      - Hollow bullets (○◦o) → `  - item` (indented sub-bullet).
      - Fake Word headings (sentences ending in `.`) → demoted to bullets.
      - Inline image tags → unwrapped to path + *Description* block.
      - Callouts & Key takeaways → GitHub-style alert blockquotes.
      - Pseudo-headings validated without false positives on notes/steps/figures.
      - Code blocks → protected (pass-through).
    """

    # ── Compiled patterns ───────────────────────────────────────────────
    _SEQ_RE       = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
    _TOPIC_RE     = re.compile(r"^(Topic\s+\d+[:\-]?.*)$", re.IGNORECASE)
    _TAKEAWAY_RE  = re.compile(r"^[✔✓✅☑]\s*", re.UNICODE)
    _SUB_BULL_RE  = re.compile(r"^[○◦o]\s+(.+)$")
    _SOLID_BULL   = re.compile(r"^[•●]\s+")
    _IMAGE_RE     = re.compile(r"!\[Image - Description: (.*?)\]\((.*?)\)")
    _BOLD_LINE_RE = re.compile(r"^\*\*(.*?)\*\*\s*$")
    _HEADING_RE   = re.compile(r"^(#{1,6})\s+(.*)$")

    def __init__(self):
        self.raw_lines: list[str] = []
        self.blueprint: dict = {
            "parents": set(),
            "sequences": [],
            "max_depth": 1,
        }

    # ── Helpers ─────────────────────────────────────────────────────────

    def _parse_seq(self, line: str):
        """Return (seq_tuple, rest_of_line) or (None, line)."""
        m = self._SEQ_RE.match(line.strip())
        if m:
            parts = tuple(int(x) for x in m.group(1).split(".") if x)
            return parts, m.group(2)
        return None, line

    @staticmethod
    def _unescape(line: str) -> str:
        """Remove Mammoth's over-aggressive backslash escaping."""
        for old, new in [
            ("\\[", "["), ("\\]", "]"),
            ("\\(", "("), ("\\)", ")"),
            ("\\$", "$"), ("\\.", "."),
            ("\\_", "_"),
            ("\\-", "-"),
            ("__", "**"),
            ("\xa0", " "),
        ]:
            line = line.replace(old, new)
        return line

    # ── Pass 1 ──────────────────────────────────────────────────────────

    def pass_one_analyse(self, text: str):
        self.raw_lines = text.splitlines()
        for line in self.raw_lines:
            seq, _ = self._parse_seq(line)
            if seq:
                self.blueprint["sequences"].append(seq)
                if len(seq) > 1:
                    self.blueprint["parents"].add(seq[:-1])
                if len(seq) > self.blueprint["max_depth"]:
                    self.blueprint["max_depth"] = len(seq)

    # ── Pass 2 ──────────────────────────────────────────────────────────

    def pass_two_transform(self) -> str:
        out: list[str] = []
        in_code = False
        lines = self.raw_lines
        i = 0

        while i < len(lines):
            line = lines[i]
            line = line.expandtabs(4)
            line_clean = line.strip()

            line_clean = re.sub(r'[\uFE0F\u20E3]', '', line_clean)

            # ── Code fence toggle ────────────────────────────────────────
            if line_clean.startswith("```"):
                in_code = not in_code
                out.append(line)
                i += 1
                continue
            if in_code:
                out.append(line)
                i += 1
                continue

            # ── Blank passthrough ─────────────────────────────────────────
            if not line_clean:
                out.append("")
                i += 1
                continue

            # ── Inline image unwrap ───────────────────────────────────────
            img_matches = list(self._IMAGE_RE.finditer(line_clean))
            if img_matches:
                for img in img_matches:
                    out.append(f"![Image]({img.group(2)})")
                    out.append("")
                    out.append(f"*Description: {img.group(1)}*")
                i += 1
                continue

            # ── Unescape (prose only, not code) ───────────────────────────
            line = self._unescape(line)
            line_clean = line.strip()

            # ── Split concatenated inline bullets ─────────────────────────
            if line_clean.startswith("- ") and " - " in line_clean[2:]:
                parts = _split_inline_bullets(line_clean)
                if len(parts) > 1:
                    out.extend(parts)
                    i += 1
                    continue

            # ── Key takeaway → blockquote ─────────────────────────────────
            if self._TAKEAWAY_RE.match(line_clean) or line_clean.lower().startswith("key takeaway"):
                norm = re.sub(r'[✔✓✅☑]', '', line_clean).strip()
                rest = norm.split(':', 1)[-1].strip() if ':' in norm else norm
                out.append(f"> **✔ Key takeaway:** {rest}")
                i += 1
                continue

            # ── Admonition Detection (Refinement 1: Multiline wrapping) ────
            adm_m = _ADMONITION_RE.match(line_clean)
            if adm_m:
                tag = _ADMONITION_MAP.get(adm_m.group(1).lower(), "NOTE")
                rest = adm_m.group(2).strip()
                # Check for subsequent contiguous prose lines
                admon_subs: list[str] = []
                j = i + 1
                while j < len(lines):
                    nxt = lines[j].strip()
                    if not nxt:
                        break
                    if nxt.startswith(("#", "```", "|", "- ", "* ", "1. ", ">")) or _ADMONITION_RE.match(nxt):
                        break
                    admon_subs.append(self._unescape(lines[j].strip()))
                    j += 1

                formatted = _format_admonition(tag, rest, admon_subs)
                out.extend(formatted)
                i = j
                continue

            # ── Hollow sub-bullet (o / ○) ─────────────────────────────────
            sub = self._SUB_BULL_RE.match(line_clean)
            if sub:
                out.append(f"  - {sub.group(1)}")
                i += 1
                continue

            # ── Solid bullet (•●) ─────────────────────────────────────────
            if self._SOLID_BULL.match(line_clean):
                out.append(self._SOLID_BULL.sub("- ", line_clean))
                i += 1
                continue

            # ── Numbered sequence — core two-pass logic ───────────────────
            seq, content = self._parse_seq(line_clean)
            if seq:
                depth = len(seq)
                is_parent = seq in self.blueprint["parents"]
                if is_parent:
                    level = min(depth + 1, 6)
                    num_str = ".".join(str(x) for x in seq)
                    out.append(f"{'#' * level} {num_str} {content}")
                else:
                    indent = "    " * (depth - 1)
                    out.append(f"{indent}1. {content}")
                i += 1
                continue

            # ── Empty parent bullet cleanup ────────────────────────────────
            if line_clean in ("-", "*", "+"):
                if i + 1 < len(lines):
                    nxt = lines[i + 1]
                    if nxt.startswith("\t- ") or nxt.startswith("    - "):
                        i += 1
                        continue
                i += 1
                continue

            # ── Fake Heading (Word style abuse: heading ending in .) ───────
            hm = self._HEADING_RE.match(line_clean)
            if hm:
                h_content = hm.group(2)
                if h_content.endswith(".") and len(h_content.split()) > 4:
                    out.append(f"- {h_content}")
                    i += 1
                    continue

            # ── Bold-only line promotion (Smarter Pseudo-Heading Heuristic) ─
            bm = self._BOLD_LINE_RE.match(line_clean)
            if bm:
                raw_inner = bm.group(1).strip()
                # Check admonitions first
                adm_bm = _ADMONITION_RE.match(raw_inner)
                if adm_bm:
                    tag = _ADMONITION_MAP.get(adm_bm.group(1).lower(), "NOTE")
                    rest = adm_bm.group(2).strip()
                    formatted = _format_admonition(tag, rest)
                    out.extend(formatted)
                    i += 1
                    continue

                if self._TOPIC_RE.match(raw_inner):
                    out.append(f"## {raw_inner}")
                    i += 1
                    continue

                seq_m = self._SEQ_RE.match(raw_inner)
                if seq_m:
                    out.append(f"### {raw_inner}")
                    i += 1
                    continue

                if _is_valid_pseudo_heading(raw_inner):
                    out.append(f"### {raw_inner}")
                    i += 1
                    continue

                out.append(line)
                i += 1
                continue

            # ── Topic pattern (plain text) ─────────────────────────────────
            if self._TOPIC_RE.match(line_clean):
                out.append(f"## {line_clean}")
                i += 1
                continue

            # ── Plain heading (surrounded by blank lines) ──────────────────
            prev_blank = (i == 0) or (not lines[i - 1].strip())
            next_blank = (i == len(lines) - 1) or (not lines[i + 1].strip())
            if _is_plain_heading(line_clean, prev_blank, next_blank):
                out.append(f"## {line_clean.rstrip(':')}")
                i += 1
                continue

            # ── Passthrough ────────────────────────────────────────────────
            out.append(line)
            i += 1

        return "\n".join(out)

    # ── Code-block, Admonition & Table Safety Net ──────────────────────

    @staticmethod
    def _final_pass(text: str) -> str:
        """Post-transform: detect unwrapped code, normalize callouts, unwrap single-cell tables."""
        text = re.sub(r"\*\*\s*\*\*", "", text)
        text = re.sub(r"\*{3,}", "**", text)
        text = _sanitize_table_cells(text)
        text = _unwrap_single_cell_pipe_tables(text)

        paras = text.split("\n\n")
        for i, p in enumerate(paras):
            stripped = p.strip()
            if not stripped:
                continue

            # ServiceNow code block auto-fencing
            if not stripped.startswith("```") and _is_servicenow_code(stripped):
                paras[i] = f"```javascript\n{stripped}\n```"
                continue

            # Refinement 1: Multiline Admonition Prefixing
            if stripped.startswith("> [!"):
                p_lines = stripped.splitlines()
                fixed_lines = []
                for pl in p_lines:
                    pl_s = pl.strip()
                    if pl_s.startswith(">"):
                        fixed_lines.append(pl_s)
                    elif pl_s:
                        fixed_lines.append(f"> {pl_s}")
                    else:
                        fixed_lines.append(">")
                paras[i] = "\n".join(fixed_lines)
                continue

            if stripped.startswith(("#", "-", "*", ">", "|", "```", "!", "[")):
                continue

            para_lines = [l for l in stripped.splitlines() if l.strip()]
            if len(para_lines) == 1 and 3 <= len(stripped) <= 70 and stripped[-1] not in ".,:;?":
                if _is_valid_pseudo_heading(stripped):
                    paras[i] = f"### {stripped}"

        return "\n\n".join(paras)

    # ── Public runner ────────────────────────────────────────────────────

    def run(self, raw_text: str) -> str:
        """Full pipeline: Pass 1 → Pass 2 → Final safety-net pass."""
        self.pass_one_analyse(raw_text)
        transformed = self.pass_two_transform()
        return self._final_pass(transformed)


def _normalize_docx_markdown(md_text: str) -> str:
    """Public shim — delegates to the two-pass normalizer."""
    return TwoPassDocumentNormalizer().run(md_text)


# ── Complex Table & Fallback Conversion Engine ────────────────────────────────

def _cell_to_html_content(cell: Any) -> str:
    """
    Serialize cell content into clean HTML, converting inline formatting
    (bold, italic, code) to standard HTML tags (<strong>, <em>, <code>, <br>).
    This satisfies Refinement 2 for seamless markdown-it-py AST parsing.
    """
    p_htmls = []
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    namespaces = {"w": w_ns}

    for p in cell.paragraphs:
        runs_html = []
        for run in p.runs:
            t = run.text
            if not t:
                continue
            escaped = html.escape(t)
            is_bold = bool(run.bold)
            is_italic = bool(run.italic)
            is_code = bool(run.font and run.font.name in ("Consolas", "Courier New", "Courier"))

            formatted = escaped
            if is_code:
                formatted = f"<code>{formatted}</code>"
            if is_bold:
                formatted = f"<strong>{formatted}</strong>"
            if is_italic:
                formatted = f"<em>{formatted}</em>"
            runs_html.append(formatted)

        p_text = "".join(runs_html)
        if not p_text and p.text.strip():
            escaped = html.escape(p.text.strip())
            escaped = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", escaped)
            escaped = re.sub(r"\*(.*?)\*", r"<em>\1</em>", escaped)
            escaped = re.sub(r"`(.*?)`", r"<code>\1</code>", escaped)
            p_text = escaped

        if p_text:
            p_htmls.append(p_text)

    return "<br>".join(p_htmls)


def _cell_to_clean_pipe_text(cell: Any) -> str:
    """Prepare cell text for standard Markdown pipe table row."""
    text = cell.text.strip().replace("\n", "<br>").replace("|", "\\|")
    return text


def _convert_table_to_markdown_or_html(table: Any) -> str:
    """
    Convert a python-docx Table to Markdown or HTML:
    - Single-cell table -> GitHub-style alert or blockquote.
    - Simple table (no merged cells) -> standard Markdown pipe table.
    - Complex table (colspans / rowspans) -> clean HTML <table> with inline HTML formatting.
    """
    if not table.rows:
        return ""

    # Check for single-cell callout box
    unique_cells_first_row = set(c._tc for c in table.rows[0].cells)
    if len(table.rows) == 1 and len(unique_cells_first_row) == 1:
        cell = table.rows[0].cells[0]
        cell_paras = [p.text.strip() for p in cell.paragraphs if p.text.strip()]
        if not cell_paras:
            return ""
        first_p = cell_paras[0]
        adm_m = _ADMONITION_RE.match(first_p)
        if adm_m:
            tag = _ADMONITION_MAP.get(adm_m.group(1).lower(), "NOTE")
            rest = adm_m.group(2).strip()
            return "\n" + "\n".join(_format_admonition(tag, rest, cell_paras[1:])) + "\n"
        else:
            lines = [f"> {p}" for p in cell_paras]
            return "\n" + "\n".join(lines) + "\n"

    # Check for complex table (merged cells)
    has_grid_span = any(bool(c._tc.xpath('./w:tcPr/w:gridSpan')) for row in table.rows for c in row.cells)
    has_v_merge = any(bool(c._tc.xpath('./w:tcPr/w:vMerge')) for row in table.rows for c in row.cells)
    has_dup_tc = any(len(set(c._tc for c in row.cells)) < len(row.cells) for row in table.rows)
    is_complex = has_grid_span or has_v_merge or has_dup_tc

    if not is_complex:
        md_lines = []
        header = table.rows[0]
        header_texts = [_cell_to_clean_pipe_text(c) for c in header.cells]
        md_lines.append("\n| " + " | ".join(header_texts) + " |")
        md_lines.append("|" + "|".join(["---"] * len(header.cells)) + "|")
        for row in table.rows[1:]:
            row_texts = [_cell_to_clean_pipe_text(c) for c in row.cells]
            md_lines.append("| " + " | ".join(row_texts) + " |")
        md_lines.append("\n")
        return "\n".join(md_lines)

    # Complex Table: HTML <table> serialization with inline HTML tags (Refinement 2)
    html_lines = ['\n<table class="docx-table">', '<tbody>']
    visited_tc: set[Any] = set()

    for r_idx, row in enumerate(table.rows):
        row_html = ['  <tr>']
        for c_idx, cell in enumerate(row.cells):
            tc = cell._tc
            if tc in visited_tc:
                continue
            visited_tc.add(tc)

            # Colspan calculation
            grid_span = tc.xpath('./w:tcPr/w:gridSpan/@w:val')
            colspan = int(grid_span[0]) if grid_span else sum(1 for c in row.cells if c._tc == tc)

            # Rowspan calculation
            rowspan = 1
            for next_r in range(r_idx + 1, len(table.rows)):
                if any(c._tc == tc for c in table.rows[next_r].cells):
                    rowspan += 1
                else:
                    break

            tag = "th" if r_idx == 0 else "td"
            attrs = []
            if colspan > 1:
                attrs.append(f'colspan="{colspan}"')
            if rowspan > 1:
                attrs.append(f'rowspan="{rowspan}"')
            attr_str = f" {' '.join(attrs)}" if attrs else ""

            cell_html = _cell_to_html_content(cell)
            row_html.append(f'    <{tag}{attr_str}>{cell_html}</{tag}>')
        row_html.append('  </tr>')
        html_lines.extend(row_html)

    html_lines.append('</tbody>')
    html_lines.append('</table>\n')
    return "\n".join(html_lines)


def _extract_paragraph_markdown(
    p: Any,
    branch_name: str = "default",
    image_dir: str | None = None,
    image_describer: Any = None,
    prefix: str = "doc"
) -> tuple[str, bool]:
    """
    Extracts text from a python-docx Paragraph element with:
    - Word hyperlink XML extraction: [Anchor](URL)
    - Inline formatting: bold (**), italic (*), code (`)
    - Embedded image drawing extraction to branch image directory
    Returns (paragraph_text, is_fully_bold).
    """
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    parts = []
    has_text = False
    all_runs_bold = True
    run_count = 0

    for child in p._element:
        tag = child.tag
        if tag.endswith("hyperlink"):
            # Hyperlink element: <w:hyperlink r:id="...">
            r_id = child.attrib.get(f"{{{r_ns}}}id")
            url = ""
            if r_id and hasattr(p, "part") and r_id in p.part.rels:
                url = p.part.rels[r_id].target_ref

            link_text = "".join(node.text for node in child.xpath(".//w:t") if node.text).strip()
            if link_text:
                has_text = True
                run_count += 1
                all_runs_bold = False
                if url:
                    parts.append(f"[{link_text}]({url})")
                else:
                    parts.append(link_text)

        elif tag.endswith("r"):
            # Check for embedded drawings/images
            blip_ids = child.xpath(".//a:blip/@r:embed")
            if blip_ids and image_dir:
                for b_id in blip_ids:
                    if hasattr(p, "part") and b_id in p.part.rels:
                        img_part = p.part.rels[b_id].target_part
                        ext = ".png"
                        if "jpeg" in img_part.content_type:
                            ext = ".jpg"
                        elif "gif" in img_part.content_type:
                            ext = ".gif"
                        filename = f"{prefix}_fb_{uuid.uuid4().hex[:6]}{ext}"
                        out_path = os.path.join(image_dir, filename)
                        rel_path = f"images/{filename}"
                        try:
                            with open(out_path, "wb") as f:
                                f.write(img_part.blob)
                        except Exception as e:
                            logger.warning(f"Failed to write image {filename}: {e}")

                        desc = None
                        if image_describer:
                            try:
                                desc = image_describer.describe_from_path(out_path)
                            except Exception as e:
                                logger.warning(f"Fallback image describe error: {e}")

                        # Refinement 3: Image Alt-Text Fallback
                        if not desc or "unavailable" in desc.lower() or "error" in desc.lower() or not desc.strip():
                            desc = f"Image: {filename} - Description Unavailable"

                        clean_desc = desc.replace("\n", " ").replace("[", "(").replace("]", ")")[:300]
                        parts.append(f"\n\n![Image - Description: {clean_desc}]({rel_path})\n\n")

            # Check text runs
            text = "".join(node.text for node in child.xpath(".//w:t") if node.text)
            if text:
                has_text = True
                run_count += 1
                is_bold = bool(child.xpath("./w:rPr/w:b[not(@w:val='0' or @w:val='false')]"))
                is_italic = bool(child.xpath("./w:rPr/w:i[not(@w:val='0' or @w:val='false')]"))
                is_code = bool(child.xpath("./w:rPr/w:rFonts[@w:ascii='Consolas' or @w:ascii='Courier New']"))

                if not is_bold:
                    all_runs_bold = False

                formatted = text
                if is_code:
                    formatted = f"`{formatted}`"
                elif is_bold and is_italic:
                    formatted = f"***{formatted}***"
                elif is_bold:
                    formatted = f"**{formatted}**"
                elif is_italic:
                    formatted = f"*{formatted}*"

                parts.append(formatted)

    full_text = "".join(parts).strip()
    is_bold_para = has_text and all_runs_bold and run_count > 0
    return full_text, is_bold_para


def _fallback_convert_docx_to_markdown(file_path: str, branch_name: str = "default") -> str:
    """
    Pure-python DOCX → Markdown conversion used when mammoth is unavailable.
    Preserves hyperlinks, detects admonitions, serializes complex tables,
    and extracts embedded images.
    """
    doc = Document(file_path)
    md_lines = []

    topic_pattern = re.compile(r"^(Topic\s+\d+[:\-]?.*)$", re.IGNORECASE)
    numbered_pattern = re.compile(r"^(\d+\.\s+[A-Z][a-zA-Z0-9\s&]+)$")

    prefix = os.path.splitext(os.path.basename(file_path))[0]
    image_dir = None
    try:
        from src.ingestion.core import get_branch_image_dir
        image_dir = get_branch_image_dir(branch_name)
    except Exception:
        pass

    image_describer = None
    try:
        from src.ingestion.image_describer import ImageDescriberAgent
        image_describer = ImageDescriberAgent()
    except Exception:
        pass

    for p in doc.paragraphs:
        style_name = p.style.name if p.style else ""
        text, is_bold_run = _extract_paragraph_markdown(
            p, branch_name=branch_name, image_dir=image_dir, image_describer=image_describer, prefix=prefix
        )
        if not text:
            continue

        raw_plain = p.text.strip()

        # Check callout / admonition first
        adm_match = _ADMONITION_RE.match(raw_plain)
        if adm_match:
            tag = _ADMONITION_MAP.get(adm_match.group(1).lower(), "NOTE")
            rest = adm_match.group(2).strip()
            md_lines.append("\n".join(_format_admonition(tag, rest)) + "\n")
            continue

        if style_name.startswith("Heading"):
            try:
                level = int(style_name.split()[-1])
                md_lines.append(f"{'#' * level} {raw_plain}\n")
            except ValueError:
                md_lines.append(f"# {raw_plain}\n")
        elif style_name == "Title":
            md_lines.append(f"# {raw_plain}\n")
        elif topic_pattern.match(raw_plain) or numbered_pattern.match(raw_plain):
            md_lines.append(f"## {raw_plain}\n")
        elif is_bold_run and _is_valid_pseudo_heading(raw_plain):
            md_lines.append(f"### {raw_plain}\n")
        elif style_name.startswith("List Bullet") or style_name == "List Paragraph":
            md_lines.append(f"- {text}")
        elif style_name.startswith("List Number"):
            md_lines.append(f"1. {text}")
        else:
            if _is_servicenow_code(raw_plain):
                md_lines.append(f"```javascript\n{raw_plain}\n```\n")
            else:
                md_lines.append(text + "\n")

    for table in doc.tables:
        table_md = _convert_table_to_markdown_or_html(table)
        if table_md:
            md_lines.append(table_md)

    raw_output = "\n".join(md_lines)
    return _normalize_docx_markdown(raw_output)


# ── Public API ─────────────────────────────────────────────────────────────────

def convert_docx_to_markdown(file_path: str, branch_name: str = "default") -> str:
    """
    Convert a DOCX file to structured Markdown using Mammoth.
    Extracts embedded images, fetches LLM descriptions with robust fallbacks,
    preserves semantic hierarchy, and formats callouts and tables.
    Falls back to a pure-python implementation if mammoth is not installed.
    """
    try:
        import mammoth
        from src.ingestion.image_describer import ImageDescriberAgent
        from src.ingestion.core import get_branch_image_dir
        import time

        image_dir = get_branch_image_dir(branch_name)
        prefix = os.path.splitext(os.path.basename(file_path))[0]

        class ImageCounter:
            def __init__(self):
                self.val = 0

        counter = ImageCounter()
        image_describer = ImageDescriberAgent()

        def _sanitize_alt(desc: str) -> str:
            desc = desc.replace("\n", " ").replace("\r", " ")
            desc = desc.replace("[", "(").replace("]", ")")
            desc = re.sub(r"\s+", " ", desc).strip()
            return desc[:300]

        def convert_image(image):
            nonlocal counter
            i = counter.val
            counter.val += 1

            ext = ".png"
            if image.content_type == "image/jpeg":
                ext = ".jpg"
            elif image.content_type == "image/gif":
                ext = ".gif"

            filename = f"{prefix}_inline_{uuid.uuid4().hex[:6]}{ext}"
            out_path = os.path.join(image_dir, filename)
            rel_path = f"images/{filename}"

            with image.open() as image_bytes:
                with open(out_path, "wb") as f:
                    f.write(image_bytes.read())

            desc = None
            try:
                if image_describer:
                    if i > 0:
                        time.sleep(1)  # Light throttle to prevent 429 rate limit spikes
                    desc = image_describer.describe_from_path(out_path)
            except Exception as e:
                logger.warning(f"Error generating description for image {filename}: {e}")

            # Refinement 3: Image Alt-Text Fallback
            if not desc or "unavailable" in desc.lower() or "error" in desc.lower() or not desc.strip():
                desc = f"Image: {filename} - Description Unavailable"

            return {"src": rel_path, "alt": f"Image - Description: {_sanitize_alt(desc)}"}

        # Convert to Markdown using Mammoth
        style_map = (
            "p[style-name='Heading 1'] => h1:fresh\n"
            "p[style-name='Heading 2'] => h2:fresh\n"
            "p[style-name='Heading 3'] => h3:fresh\n"
            "p[style-name='Title'] => h1:fresh\n"
            "p[style-name='Subtitle'] => h2:fresh\n"
            "p[style-name='Code'] => pre:fresh\n"
            "p[style-name='HTML Preformatted'] => pre:fresh\n"
            "p[style-name='Source Code'] => pre:fresh"
        )
        with open(file_path, "rb") as docx_file:
            result = mammoth.convert_to_markdown(
                docx_file,
                style_map=style_map,
                convert_image=mammoth.images.img_element(convert_image)
            )
            raw_md = result.value

        normalized_md = _normalize_docx_markdown(raw_md)
        return normalized_md

    except ImportError:
        logger.warning("mammoth package not found. Using fallback DOCX to Markdown converter.")
        return _fallback_convert_docx_to_markdown(file_path, branch_name=branch_name)
