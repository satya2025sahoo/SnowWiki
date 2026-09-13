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
    BULLET_CHARS = ("-", "*", "+", "•", "●", "▪", "■", "◆", "o", "○", "◦", "✔", "✓")
    _BULLET_RE = re.compile(rf"^([{re.escape(''.join(BULLET_CHARS))}]+)\s+")
    
    # Matches numbered sequences like "1.", "1.1", "1.1.1" etc.
    _NUMBERED_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
    
    # Matches heading lines (already containing #)
    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
    
    # Glued line rule: Sentence ends with . or ) followed by Space and Title-Case with a colon
    # E.g.: "Key: Most Granular. ML Connection Suggestions:" -> split after period
    _GLUED_LINE_RE = re.compile(r"^(.*?[.\]\)])\s+([A-Z][a-zA-Z0-9\s&]+:.*)$")
    
    # Label: Value rule (e.g. "Effort: Medium touch")
    _LABEL_VALUE_RE = re.compile(r"^(\**[A-Z][a-zA-Z0-9\s&]+:\**)\s+(.+)$")
    
    # Admonition/Callouts
    _CALLOUT_RE = re.compile(r"^(✔\s*Key takeaway:|Key takeaway:|Note:|Warning:|Important:|Caution:|Tip:)\s*(.*)", re.IGNORECASE)

    def __init__(self, raw_markdown: str):
        self.raw_markdown = raw_markdown
        self.lines: List[str] = []
        self.protected_blocks: dict[str, str] = {}
        
        # Heading Stack: [(level, heading_text), ...]
        self.heading_stack: List[Tuple[int, str]] = []
        self.has_h1 = False
    
    def process(self) -> str:
        # Pass 0: Protect code blocks and tables
        self._protect_blocks()
        
        # Pass 1: Initial split, glued lines, callouts, basic bullets
        self._pass1_preclean()
        
        # Pass 2: Wrap recovery (stitch broken lists)
        self._pass2_stitch_wraps()
        
        # Pass 3: Resolve Headings & Hierarchy
        self._pass3_resolve_hierarchy()
        
        # Pass 4: Unmask protected blocks and normalize spacing
        result = self._pass4_assemble()
        
        return result

    # ── Pass 0: Protect ───────────────────────────────────────────────────
    def _protect_blocks(self):
        """Finds tables and fenced code blocks, replaces them with UUID markers."""
        lines = self.raw_markdown.splitlines()
        protected = []
        
        in_code = False
        in_table = False
        current_block = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            line_s = line.strip()
            
            # Code block toggle
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
                
            # Table logic (very simple start with |)
            if line_s.startswith("|"):
                if not in_table:
                    in_table = True
                    current_block = [line]
                else:
                    current_block.append(line)
                i += 1
                continue
            elif in_table:
                # End of table
                in_table = False
                marker = f"__PROTECTED_{uuid.uuid4().hex}__"
                self.protected_blocks[marker] = "\n".join(current_block)
                protected.append(marker)
                current_block = []
                
            protected.append(line)
            i += 1
            
        if current_block: # flush
            marker = f"__PROTECTED_{uuid.uuid4().hex}__"
            self.protected_blocks[marker] = "\n".join(current_block)
            protected.append(marker)
            
        self.lines = protected

    # ── Pass 1: Pre-clean ─────────────────────────────────────────────────
    def _pass1_preclean(self):
        """Splits glued lines, normalizes bullets, detects callouts."""
        new_lines = []
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            if line.startswith("__PROTECTED_"):
                new_lines.append(line)
                i += 1
                continue
                
            clean = line.strip()
            if not clean:
                new_lines.append(line)
                i += 1
                continue
                
            # Glued line split (Rule 8)
            m_glue = self._GLUED_LINE_RE.match(clean)
            if m_glue:
                part1, part2 = m_glue.groups()
                if part2.endswith(":"):
                    clean = part1
                    self.lines.insert(i + 1, part2)
            
            # Inline Note split (e.g. "Value. Note: XYZ")
            m_inline_note = re.match(r"^(.*?[.\]\)])\s+(Note:|Warning:|Important:|Tip:|Caution:)\s*(.*)$", clean, re.IGNORECASE)
            if m_inline_note:
                part1, note_lbl, note_val = m_inline_note.groups()
                clean = part1
                self.lines.insert(i + 1, f"{note_lbl} {note_val}")
            
            # Callout Promotion (Rule 13)
            m_callout = self._CALLOUT_RE.match(clean)
            if m_callout:
                prefix = m_callout.group(1).lower()
                content = m_callout.group(2).strip()
                tag = "NOTE"
                if "takeaway" in prefix or "tip" in prefix: tag = "TIP"
                elif "warn" in prefix or "caution" in prefix: tag = "WARNING"
                elif "important" in prefix: tag = "IMPORTANT"
                
                new_lines.append(f"> [!{tag}]")
                if content:
                    new_lines.append(f"> {content}")
                i += 1
                continue
                
            # Bullet cleanup (Rule 12)
            m_bull = self._BULLET_RE.match(clean)
            if m_bull:
                content = clean[len(m_bull.group(1)):].strip()
                if content.startswith(("•", "●", "✔", "✓")):
                    content = content[1:].strip()
                
                # Check Label Value inside bullet
                m_label = self._LABEL_VALUE_RE.match(content)
                if m_label:
                    label, val = m_label.groups()
                    if not label.startswith("**"):
                        label = f"**{label}**"
                    new_lines.append(f"- {label} {val}")
                else:
                    new_lines.append(f"- {content}")
                i += 1
                continue
                
            # Label Value (Rule 7) without bullet
            m_label = self._LABEL_VALUE_RE.match(clean)
            if m_label and not clean.startswith(("#", ">")):
                label, val = m_label.groups()
                if not label.startswith("**"):
                    label = f"**{label}**"
                new_lines.append(f"- {label} {val}")
                i += 1
                continue
            
            new_lines.append(clean)
            i += 1
            
        self.lines = new_lines

    # ── Pass 2: Wrap Recovery ─────────────────────────────────────────────
    def _pass2_stitch_wraps(self):
        """Stitches bullet lines that wrap mid-sentence (Rule 11)."""
        new_lines = []
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            
            # Look for a bullet that ends abruptly
            if line.strip().startswith("- ") and i + 1 < len(self.lines):
                content = line.strip()[2:].strip()
                # End abruptly? Not a period, not colon, length > 10
                if content and content[-1] not in ".!:;" and len(content) > 10:
                    next_line = self.lines[i+1].strip()
                    # If next line is a bullet but starts with lowercase or continuation word
                    if next_line.startswith("- "):
                        next_content = next_line[2:].strip()
                        if next_content and (next_content[0].islower() or next_content.split()[0] in {"and", "or", "in", "to", "with", "for"}):
                            # Stitch!
                            stitched = f"{line.rstrip()} {next_content}"
                            new_lines.append(stitched)
                            i += 2
                            continue
            
            new_lines.append(line)
            i += 1
        self.lines = new_lines

    # ── Pass 3: Hierarchy ─────────────────────────────────────────────────
    def _pass3_resolve_hierarchy(self):
        """Core hierarchy engine (Rules 1-6, 9, 10, 14, 15)."""
        new_lines = []
        
        for i, line in enumerate(self.lines):
            if line.startswith("__PROTECTED_") or line.strip() == "":
                new_lines.append(line)
                continue
                
            clean = line.strip()
            
            # Rule 6: Bullets are always body
            if clean.startswith(("-", "*", ">", "![", "[")):
                new_lines.append(line)
                continue

            is_isolated = self._is_isolated(i)
            has_heading_marker = clean.startswith("#")
            has_number = self._NUMBERED_RE.match(clean.lstrip("# \t"))
            
            is_candidate = has_heading_marker or (is_isolated and not clean.endswith((".", ",", ";")))
            
            if is_candidate:
                # Strip existing # and colon
                m_heading = self._HEADING_RE.match(clean)
                inner_text = m_heading.group(2) if m_heading else clean
                
                # Rule 14: Strip trailing colon
                if inner_text.endswith(":"):
                    inner_text = inner_text[:-1].strip()
                
                target_level = self._determine_level(inner_text, has_number)
                new_lines.append(f"{'#' * target_level} {inner_text}")
            else:
                # Rule 4: Paragraph follows number / pure body text
                new_lines.append(line)
                
        self.lines = new_lines

    def _is_isolated(self, index: int) -> bool:
        prev_blank = (index == 0) or (self.lines[index-1].strip() == "")
        next_blank = (index == len(self.lines) - 1) or (self.lines[index+1].strip() == "")
        return prev_blank and next_blank
        
    def _determine_level(self, text: str, m_number) -> int:
        target_level = 2
        
        if m_number:
            # Rule 3: Numbering depth
            seq_str = m_number.group(1)
            depth = len(seq_str.split("."))
            
            # Rule 5: Reset Rule - if numbering restarts at 1
            if seq_str == "1":
                # It's a new list under the current top of stack
                parent_level = self.heading_stack[-1][0] if self.heading_stack else 1
                target_level = min(parent_level + 1, 6)
            else:
                # Check for sibling in stack with same digit depth
                # Heuristic: base it on the parent unnumbered heading + depth
                parent_level = 1
                for lvl, title in reversed(self.heading_stack):
                    if not self._NUMBERED_RE.match(title):
                        parent_level = lvl
                        break
                target_level = min(parent_level + depth, 6)
                
        else:
            # Top-level candidate
            if not self.has_h1:
                target_level = 1
                self.has_h1 = True
            else:
                target_level = 2
                
        # Rule 15: Clamp jumps
        parent_level = self.heading_stack[-1][0] if self.heading_stack else 1
        if target_level > parent_level + 1:
            target_level = parent_level + 1
            
        # Rule 9: Stack management
        while self.heading_stack and self.heading_stack[-1][0] >= target_level:
            self.heading_stack.pop()
        self.heading_stack.append((target_level, text))
        
        return target_level

    # ── Pass 4: Assemble ──────────────────────────────────────────────────
    def _pass4_assemble(self) -> str:
        out = []
        for line in self.lines:
            if line.startswith("__PROTECTED_"):
                # Unmask
                out.append(self.protected_blocks[line])
            else:
                out.append(line)
                
        # Fix blank line spacing around headings
        assembled = []
        for line in out:
            # Flatten multi-line protected blocks so we can inspect lines
            for subline in line.splitlines():
                assembled.append(subline)
                
        final_lines = []
        for i, line in enumerate(assembled):
            stripped = line.strip()
            is_heading = stripped.startswith("#")
            
            if is_heading and final_lines and final_lines[-1].strip() != "":
                final_lines.append("")
                
            final_lines.append(line)
            
            if is_heading and i < len(assembled) - 1 and assembled[i+1].strip() != "":
                final_lines.append("")
                
        # Collapse >2 blanks
        text = "\n".join(final_lines)
        return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"

def structure_markdown(text: str) -> str:
    """Entry point for the PDF markdown structurer engine."""
    engine = DocumentStructurer(text)
    return engine.process()
