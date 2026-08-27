import sys
import os
import pytest
from src.ingestion.docx_utils import _normalize_docx_markdown, _is_servicenow_code
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

def test_multi_line_table_cell_sanitization():
    md = "| Header 1 |\n|---|\n| Line 1\\nLine 2 |"
    norm = _normalize_docx_markdown(md)
    assert "| Line 1<br>Line 2 |" in norm

def test_context_aware_unescaping():
    md = "Avoid \\[ and \\$ in text.\n```javascript\nvar regex = /\\[0-9\\]/;\n```"
    norm = _normalize_docx_markdown(md)
    assert "Avoid [ and $ in text." in norm
    assert "var regex = /\\[0-9\\]/;" in norm

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
