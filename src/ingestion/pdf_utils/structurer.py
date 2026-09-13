"""
src/ingestion/pdf_utils/structurer.py
======================================
Implements 16 structuring rules for messy PDF Markdown conversions.
Fixes erratic heading depths, split bullets, glued lines, and applies consistent numbering trees.
"""

import re
import uuid
from typing import List, Tuple


class DocumentStructurer:
    # ── Constants & Patterns ───────────────────────────────────────────────

    # Match a bullet marker at the START of stripped content
    _BULL_MARKER_RE = re.compile(r"^([\-\*\+•●▪■◆○◦✔✓]+)\s+")

    # Matches numbered sequences like "1.", "1.1", "1.1.1" etc.
    _NUMBERED_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")

    # Matches heading lines (already containing #)
    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

    # Glued line rule: Sentence ends with . followed by a multi-word Title-Case label ending in colon.
    # Requires ≥2 words before the colon to avoid spurious splits on "e.g. Foo:".
    _GLUED_LINE_RE = re.compile(
        r"^(.*?[.\]\)])\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Za-z0-9&]+)+:.*)$"
    )

    # Label: Value rule (e.g. "Effort: Medium touch")
    _LABEL_VALUE_RE = re.compile(r"^(\**[A-Z][a-zA-Z0-9\s&]+:\**)\s+(.+)$")

    # Admonition/Callouts
    _CALLOUT_RE = re.compile(
        r"^(✔\s*Key takeaway:|Key takeaway:|Note:|Warning:|Important:|Caution:|Tip:)\s*(.*)",
        re.IGNORECASE,
    )

    # Trailing OCR fragment: 1-4 Title-Case words ending with period (no comma / colon inside)
    _FRAGMENT_RE = re.compile(r"^(?:[A-Z][a-zA-Z0-9]*\s?){1,4}\.\s*$")

    # Inline note mid-bullet (e.g. "... sub-classes. Note: ...")
    _INLINE_NOTE_RE = re.compile(
        r"^(.*?[.\]\)])\s+(Note:|Warning:|Important:|Tip:|Caution:)\s*(.*)$",
        re.IGNORECASE,
    )

    def __init__(self, raw_markdown: str):
        self.raw_markdown = raw_markdown
        self.lines: List[str] = []
        self.protected_blocks: dict[str, str] = {}

        # Heading Stack: [(level, heading_text), ...]
        self.heading_stack: List[Tuple[int, str]] = []
        self.has_h1 = False

    def process(self) -> str:
        self._protect_blocks()       # Pass 0: Mask code / tables
        self._pass1_preclean()       # Pass 1: Glue-split, bullets, callouts
        self._pass2_stitch_wraps()   # Pass 2: Stitch OCR fragments & wrap breaks
        self._pass3_resolve_hierarchy()  # Pass 3: Heading levels
        return self._pass4_assemble()    # Pass 4: Reassemble & spacing

    # ─────────────────────────────────────────────────────────────────────
    # Pass 0 – Protect code blocks and tables
    # ─────────────────────────────────────────────────────────────────────
    def _protect_blocks(self):
        lines = self.raw_markdown.splitlines()
        protected: List[str] = []
        in_code = False
        in_table = False
        current_block: List[str] = []

        i = 0
        while i < len(lines):
            line = lines[i]
            line_s = line.strip()

            # Code fence toggle
            if line_s.startswith("```"):
                if not in_code:
                    in_code = True
                    current_block = [line]
                else:
                    in_code = False
                    current_block.append(line)
                    marker = f"__PROTECTED_{uuid.uuid4().hex}__"
                    self.protected_blocks[marker] = "\n".join(current_block)
                    protected.append(marker)
                    current_block = []
                i += 1
                continue

            if in_code:
                current_block.append(line)
                i += 1
                continue

            # Table (lines starting with |)
            if line_s.startswith("|"):
                if not in_table:
                    in_table = True
                    current_block = [line]
                else:
                    current_block.append(line)
                i += 1
                continue
            elif in_table:
                in_table = False
                marker = f"__PROTECTED_{uuid.uuid4().hex}__"
                self.protected_blocks[marker] = "\n".join(current_block)
                protected.append(marker)
                current_block = []

            protected.append(line)
            i += 1

        if current_block:  # flush unclosed block
            marker = f"__PROTECTED_{uuid.uuid4().hex}__"
            self.protected_blocks[marker] = "\n".join(current_block)
            protected.append(marker)

        self.lines = protected

    # ─────────────────────────────────────────────────────────────────────
    # Pass 1 – Pre-clean: normalise bullets (with indent), glue-splits, callouts
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _get_indent(line: str) -> str:
        """Return leading whitespace from a line (tabs expanded to 2 spaces each)."""
        expanded = line.expandtabs(2)
        m = re.match(r"^(\s*)", expanded)
        return m.group(1) if m else ""

    @staticmethod
    def _indent_depth(indent: str) -> int:
        """Every 2 spaces = 1 nesting level."""
        return len(indent) // 2

    @staticmethod
    def _make_indent(depth: int) -> str:
        return "  " * depth

    def _pass1_preclean(self):
        """
        • Preserves 2-space indent on nested bullets so `  - Sub` stays `  - Sub`.
        • Splits glued lines embedded inside bullet content.
        • Detects callouts.
        • Applies Label:Value bolding (Rule 7).
        """
        new_lines: List[str] = []
        i = 0
        while i < len(self.lines):
            line = self.lines[i]

            if line.startswith("__PROTECTED_"):
                new_lines.append(line)
                i += 1
                continue

            # ── Measure indent BEFORE stripping ─────────────────────────
            indent_str = self._get_indent(line)
            depth = self._indent_depth(indent_str)
            norm_indent = self._make_indent(depth)

            clean = line.strip()
            if not clean:
                new_lines.append("")
                i += 1
                continue

            # ── Is this line a bullet? ───────────────────────────────────
            m_bull = self._BULL_MARKER_RE.match(clean)
            if m_bull:
                content = clean[len(m_bull.group(0)):].strip()

                # Strip duplicate OCR bullet prefix (e.g. "- • item")
                if content.startswith(("•", "●", "✔", "✓")):
                    content = content[1:].strip()

                # Rule 8 (inside bullet): glued "Text. Multi Word Label: rest"
                m_glue_bull = self._GLUED_LINE_RE.match(content)
                if m_glue_bull:
                    part1, part2 = m_glue_bull.groups()
                    # Apply Label:Value bolding to part1 too
                    m_lv1 = self._LABEL_VALUE_RE.match(part1.strip())
                    if m_lv1:
                        lbl1, val1 = m_lv1.groups()
                        if not lbl1.startswith("**"): lbl1 = f"**{lbl1}**"
                        part1_out = f"{lbl1} {val1}"
                    else:
                        part1_out = part1.strip()
                    new_lines.append(f"{norm_indent}- {part1_out}")
                    # Insert part2 at ROOT (no indent) to be processed next iteration
                    m_lv = self._LABEL_VALUE_RE.match(part2)
                    if m_lv:
                        lbl, val = m_lv.groups()
                        if not lbl.startswith("**"):
                            lbl = f"**{lbl}**"
                        self.lines.insert(i + 1, f"- {lbl} {val}")
                    else:
                        self.lines.insert(i + 1, part2)
                    i += 1
                    continue

                # Inline note mid-bullet: "... sub-classes. Note: xyz"
                m_note = self._INLINE_NOTE_RE.match(content)
                if m_note:
                    pre, note_lbl, note_val = m_note.groups()
                    # Apply Label:Value bolding to pre too
                    m_lv_pre = self._LABEL_VALUE_RE.match(pre.strip())
                    if m_lv_pre:
                        lbl_p, val_p = m_lv_pre.groups()
                        if not lbl_p.startswith("**"): lbl_p = f"**{lbl_p}**"
                        pre_out = f"{lbl_p} {val_p}"
                    else:
                        pre_out = pre.strip()
                    new_lines.append(f"{norm_indent}- {pre_out}")
                    self.lines.insert(i + 1, f"{note_lbl} {note_val.strip()}")
                    i += 1
                    continue

                # Rule 7 (inside bullet): "Label: value" → bold label
                m_label = self._LABEL_VALUE_RE.match(content)
                if m_label:
                    lbl, val = m_label.groups()
                    if not lbl.startswith("**"):
                        lbl = f"**{lbl}**"
                    new_lines.append(f"{norm_indent}- {lbl} {val}")
                else:
                    new_lines.append(f"{norm_indent}- {content}")
                i += 1
                continue

            # ── Non-bullet line ──────────────────────────────────────────

            # Rule 8: glued "Sentence. Multi Word Label:" on bare text
            m_glue = self._GLUED_LINE_RE.match(clean)
            if m_glue:
                part1, part2 = m_glue.groups()
                if part2.endswith(":"):
                    clean = part1
                    self.lines.insert(i + 1, part2)
                else:
                    # has content after colon
                    new_lines.append(part1)
                    m_lv = self._LABEL_VALUE_RE.match(part2)
                    if m_lv:
                        lbl, val = m_lv.groups()
                        if not lbl.startswith("**"):
                            lbl = f"**{lbl}**"
                        self.lines.insert(i + 1, f"- {lbl} {val}")
                    else:
                        self.lines.insert(i + 1, part2)
                    i += 1
                    continue

            # Inline note on bare text
            m_note = self._INLINE_NOTE_RE.match(clean)
            if m_note:
                part1, note_lbl, note_val = m_note.groups()
                clean = part1
                self.lines.insert(i + 1, f"{note_lbl} {note_val.strip()}")

            # Rule 13: Callout promotion
            m_callout = self._CALLOUT_RE.match(clean)
            if m_callout:
                prefix = m_callout.group(1).lower()
                content = m_callout.group(2).strip()
                tag = "NOTE"
                if "takeaway" in prefix or "tip" in prefix:
                    tag = "TIP"
                elif "warn" in prefix or "caution" in prefix:
                    tag = "WARNING"
                elif "important" in prefix:
                    tag = "IMPORTANT"
                new_lines.append(f"> [!{tag}]")
                if content:
                    new_lines.append(f"> {content}")
                i += 1
                continue

            # Rule 7: bare "Label: value" line → promote to bullet
            m_label = self._LABEL_VALUE_RE.match(clean)
            if m_label and not clean.startswith(("#", ">")):
                lbl, val = m_label.groups()
                if not lbl.startswith("**"):
                    lbl = f"**{lbl}**"
                new_lines.append(f"- {lbl} {val}")
                i += 1
                continue

            new_lines.append(clean)
            i += 1

        self.lines = new_lines

    # ─────────────────────────────────────────────────────────────────────
    # Pass 2 – Wrap Recovery & OCR Fragment Merge
    # ─────────────────────────────────────────────────────────────────────
    def _pass2_stitch_wraps(self):
        """
        Two sub-rules applied only to TOP-LEVEL (unindented) bullets:

        (b) OCR fragment merge:
            `- Application.` + `- **Service:** Logical rep…`
            → `- **Application Service:** Logical rep…`

        (a) Standard mid-sentence wrap:
            Bullet ends without terminal punctuation, next bullet starts
            with a lowercase word or common joining word.
        """
        new_lines: List[str] = []
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            stripped = line.strip()

            # Only process unindented top-level bullets
            is_top_bullet = stripped.startswith("- ") and not line.startswith("  ")

            if is_top_bullet and i + 1 < len(self.lines):
                content = stripped[2:].strip()
                next_line = self.lines[i + 1].strip()

                # (b) OCR fragment merge
                if self._FRAGMENT_RE.match(content) and next_line.startswith("- "):
                    next_content = next_line[2:].strip()
                    m_lv = self._LABEL_VALUE_RE.match(next_content)
                    if m_lv:
                        fragment_text = content.rstrip(".").strip()
                        lbl, val = m_lv.groups()
                        # Strip existing ** markers before merging (avoid double-bolding)
                        lbl_clean = lbl.strip("*").strip()   # e.g. "**Service:**" -> "Service:"
                        compound = f"{fragment_text} {lbl_clean}"  # "Application Service:"
                        if not compound.startswith("**"):
                            compound = f"**{compound}**"
                        new_lines.append(f"- {compound} {val}")
                        i += 2
                        continue

                # (a) Standard mid-sentence wrap
                if content and content[-1] not in ".!:;" and len(content) > 10:
                    if next_line.startswith("- "):
                        next_content = next_line[2:].strip()
                        if next_content and (
                            next_content[0].islower()
                            or next_content.split()[0] in {"and", "or", "in", "to", "with", "for"}
                        ):
                            new_lines.append(f"{line.rstrip()} {next_content}")
                            i += 2
                            continue

            new_lines.append(line)
            i += 1
        self.lines = new_lines

    # ─────────────────────────────────────────────────────────────────────
    # Pass 3 – Heading Hierarchy Resolution
    # ─────────────────────────────────────────────────────────────────────
    def _pass3_resolve_hierarchy(self):
        """Core hierarchy engine (Rules 1–6, 9, 10, 14, 15)."""
        new_lines: List[str] = []

        for i, line in enumerate(self.lines):
            if line.startswith("__PROTECTED_") or line.strip() == "":
                new_lines.append(line)
                continue

            clean = line.strip()

            # Rule 6: bullets, images, blockquotes are always body content
            if clean.startswith(("-", "*", ">", "![", "[")):
                new_lines.append(line)
                continue

            is_isolated = self._is_isolated(i)
            has_heading_marker = clean.startswith("#")
            has_number = self._NUMBERED_RE.match(clean.lstrip("# \t"))

            is_candidate = has_heading_marker or (
                is_isolated and not clean.endswith((".", ",", ";"))
            )

            if is_candidate:
                m_heading = self._HEADING_RE.match(clean)
                inner_text = m_heading.group(2) if m_heading else clean
                # Rule 14: strip trailing colon from headings
                if inner_text.endswith(":"):
                    inner_text = inner_text[:-1].strip()
                target_level = self._determine_level(inner_text, has_number)
                new_lines.append(f"{'#' * target_level} {inner_text}")
            else:
                new_lines.append(line)

        self.lines = new_lines

    def _is_isolated(self, index: int) -> bool:
        prev_blank = (index == 0) or (self.lines[index - 1].strip() == "")
        next_blank = (index == len(self.lines) - 1) or (self.lines[index + 1].strip() == "")
        return prev_blank and next_blank

    def _determine_level(self, text: str, m_number) -> int:
        if m_number:
            seq_str = m_number.group(1)
            depth = len(seq_str.split("."))

            if seq_str == "1":
                parent_level = self.heading_stack[-1][0] if self.heading_stack else 1
                target_level = min(parent_level + 1, 6)
            else:
                parent_level = 1
                for lvl, title in reversed(self.heading_stack):
                    if not self._NUMBERED_RE.match(title):
                        parent_level = lvl
                        break
                target_level = min(parent_level + depth, 6)
        else:
            if not self.has_h1:
                target_level = 1
                self.has_h1 = True
            else:
                target_level = 2

        # Rule 15: clamp depth jumps to at most 1
        parent_level = self.heading_stack[-1][0] if self.heading_stack else 1
        if target_level > parent_level + 1:
            target_level = parent_level + 1

        # Rule 9: maintain heading stack
        while self.heading_stack and self.heading_stack[-1][0] >= target_level:
            self.heading_stack.pop()
        self.heading_stack.append((target_level, text))

        return target_level

    # ─────────────────────────────────────────────────────────────────────
    # Pass 4 – Assemble, unmask, normalize blank lines
    # ─────────────────────────────────────────────────────────────────────
    def _pass4_assemble(self) -> str:
        out: List[str] = []
        for line in self.lines:
            if line.startswith("__PROTECTED_"):
                out.append(self.protected_blocks[line])
            else:
                out.append(line)

        # Flatten & add blank lines before/after headings
        assembled: List[str] = []
        for chunk in out:
            for subline in chunk.splitlines():
                assembled.append(subline)

        final_lines: List[str] = []
        for i, line in enumerate(assembled):
            stripped = line.strip()
            is_heading = stripped.startswith("#")

            if is_heading and final_lines and final_lines[-1].strip() != "":
                final_lines.append("")

            final_lines.append(line)

            if is_heading and i < len(assembled) - 1 and assembled[i + 1].strip() != "":
                final_lines.append("")

        text = "\n".join(final_lines)
        return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def structure_markdown(text: str) -> str:
    """Public entry point for the PDF markdown structurer engine."""
    engine = DocumentStructurer(text)
    return engine.process()
