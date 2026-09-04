import re
from src.ingestion.docx_utils.heuristics import _is_servicenow_code, _is_valid_pseudo_heading, _is_plain_heading
from src.ingestion.docx_utils.admonitions import _ADMONITION_MAP, _ADMONITION_RE, _format_admonition, _unwrap_single_cell_pipe_tables
from src.ingestion.docx_utils.tables import _sanitize_table_cells


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
