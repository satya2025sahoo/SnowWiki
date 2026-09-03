import sys
import os
import pytest
from docx import Document
from src.ingestion.docx_utils import (
    _normalize_docx_markdown,
    _is_servicenow_code,
    _is_valid_pseudo_heading,
    _convert_table_to_markdown_or_html,
)
from src.ingestion.chunking import process_markdown_for_parent_child


def test_servicenow_code_detection():
    # High confidence
    assert _is_servicenow_code("var gr = new GlideRecord('incident');")
    assert _is_servicenow_code("g_form.setValue('state', 2);")
    assert _is_servicenow_code("var parsed = JSON.parse(str);")

    # Multi-match
    assert _is_servicenow_code("function onLoad() {\n return false;\n}")

    # Negative
    assert not _is_servicenow_code("This is a function of the application.")


def test_heading_hierarchy_normalization():
    md = "**Topic 1: Initialization**\nSome text.\n**1. Overview**\nMore text."
    norm = _normalize_docx_markdown(md)
    assert "## Topic 1: Initialization" in norm
    assert "### 1. Overview" in norm


def test_pseudo_heading_rejection():
    # Notes, figures, steps, tables, and punctuation must NOT become ### headings
    assert not _is_valid_pseudo_heading("Note:")
    assert not _is_valid_pseudo_heading("Note: Be careful")
    assert not _is_valid_pseudo_heading("Figure 1: Architecture Diagram")
    assert not _is_valid_pseudo_heading("Table 2: Data Dictionary")
    assert not _is_valid_pseudo_heading("Step 1: Download files")
    assert not _is_valid_pseudo_heading("This is a long sentence ending in a period.")

    md = """**Figure 1: Architecture Diagram**
Some descriptive text.

**Table 1: User Roles**
Table details.

**Step 2: Configuration**
Step details.
"""
    norm = _normalize_docx_markdown(md)
    assert "### Figure 1" not in norm
    assert "### Table 1" not in norm
    assert "### Step 2" not in norm


def test_admonition_conversion_and_multiline():
    # Refinement 1: Multiline admonition with every line prefixed by '>'
    md = """**Note:** This is the first line of the note.
This is the second line of the note.

**Warning:** GlideRecord deleteMultiple is dangerous!

**Important:** Back up your database before upgrading.
"""
    norm = _normalize_docx_markdown(md)
    assert "> [!NOTE]" in norm
    assert "> This is the first line of the note." in norm
    assert "> This is the second line of the note." in norm
    assert "> [!WARNING]" in norm
    assert "> GlideRecord deleteMultiple is dangerous!" in norm
    assert "> [!IMPORTANT]" in norm
    assert "> Back up your database before upgrading." in norm


def test_single_cell_pipe_table_unwrapping():
    md = """| Note: Always verify credentials before deployment |
| --- |
"""
    norm = _normalize_docx_markdown(md)
    assert "| Note:" not in norm
    assert "> [!NOTE]" in norm
    assert "> Always verify credentials before deployment" in norm


def test_multi_line_table_cell_sanitization():
    md = "| Header 1 |\n|---|\n| Line 1\\nLine 2 |"
    norm = _normalize_docx_markdown(md)
    assert "| Line 1<br>Line 2 |" in norm


def test_context_aware_unescaping():
    md = "Avoid \\[ and \\$ in text.\n```javascript\nvar regex = /\\[0-9\\]/;\n```"
    norm = _normalize_docx_markdown(md)
    assert "Avoid [ and $ in text." in norm
    assert "var regex = /\\[0-9\\]/;" in norm


def test_complex_table_serialization():
    # Test simple table vs complex (merged) table
    doc = Document()

    # 1. Simple 2x2 table
    simple_table = doc.add_table(rows=2, cols=2)
    simple_table.rows[0].cells[0].text = "Header A"
    simple_table.rows[0].cells[1].text = "Header B"
    simple_table.rows[1].cells[0].text = "Data 1"
    simple_table.rows[1].cells[1].text = "Data 2"

    simple_md = _convert_table_to_markdown_or_html(simple_table)
    assert "| Header A | Header B |" in simple_md
    assert "<table" not in simple_md

    # 2. Complex table with merged horizontal cell (colspan)
    complex_table = doc.add_table(rows=2, cols=2)
    # Merge cells horizontally in row 0
    complex_table.rows[0].cells[0].merge(complex_table.rows[0].cells[1])
    complex_table.rows[0].cells[0].text = "Merged Header"

    # Add formatted runs in row 1 cell 0 (Refinement 2: inline HTML tags)
    r1c0 = complex_table.rows[1].cells[0]
    p = r1c0.paragraphs[0]
    run_b = p.add_run("Bold Value")
    run_b.bold = True
    p.add_run(" and normal")

    complex_table.rows[1].cells[1].text = "Cell 1,1"

    complex_html = _convert_table_to_markdown_or_html(complex_table)
    assert '<table class="docx-table">' in complex_html
    assert 'colspan="2"' in complex_html
    assert '<strong>Bold Value</strong>' in complex_html


def test_ast_block_chunking():
    md = """## Topic 1: Testing

```javascript
function onLoad() {
    console.log('hi');
}
```

Some paragraph here.
"""
    parents, children = process_markdown_for_parent_child(md, "test.md", "main")
    assert len(parents) > 0
    assert len(children) > 0
    child_text = children[0]["chunk_text"]
    assert "function onLoad" in child_text


def test_fallback_paragraph_formatting_and_hyperlink():
    from src.ingestion.docx_utils import _extract_paragraph_markdown
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls

    doc = Document()
    p = doc.add_paragraph()
    r1 = p.add_run("Refer to ")
    
    # Add external hyperlink relationship
    rel_id = p.part.relate_to(
        "https://docs.servicenow.com",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True
    )
    hyperlink_elm = parse_xml(
        f'<w:hyperlink {nsdecls("w", "r")} r:id="{rel_id}">'
        f'<w:r><w:t>ServiceNow Docs</w:t></w:r>'
        f'</w:hyperlink>'
    )
    p._element.append(hyperlink_elm)

    r2 = p.add_run(" for ")
    r3 = p.add_run("GlideRecord API")
    r3.bold = True

    text, is_bold = _extract_paragraph_markdown(p)
    assert "[ServiceNow Docs](https://docs.servicenow.com)" in text
    assert "**GlideRecord API**" in text
    assert not is_bold

