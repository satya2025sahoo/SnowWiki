import html
import re
from typing import Any

from src.ingestion.docx_utils.admonitions import _ADMONITION_RE, _ADMONITION_MAP, _format_admonition


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


def _cell_to_html_content(cell: Any) -> str:
    """
    Serialize cell content into clean HTML, converting inline formatting
    (bold, italic, code) to standard HTML tags (<strong>, <em>, <code>, <br>).
    This satisfies Refinement 2 for seamless markdown-it-py AST parsing.
    """
    p_htmls = []
    # w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    # namespaces = {"w": w_ns}

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
