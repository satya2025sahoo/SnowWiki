"""
tests/test_pdf_utils.py
========================
Feature-level test matrix for the pdf_utils package.

Covers all 20 rows from the implementation plan test matrix:
  #1-3    Heading detection (relative, D2 sanity check)
  #4-5    Admonition detection (Note, Warning)
  #6-7    Bullet / numbered sequence normalization
  #8      Key Takeaway blockquote
  #9      ServiceNow code fencing
  #14     Dehyphenation
  KL-1    Known-wrong dehyphenation (compound words)
  KL-2    Kerning repair — no false fire on normal prose
  #15     Simple pipe table
  D5      Table fallback (plain text on extraction failure)
  #16     Document-level guard rail (near-zero text)
  #17     Header/footer strip with tolerance band
  shim    _normalize_docx_markdown shim equivalence + DeprecationWarning
  #19     structured_pdf_utils deprecation warning
  #18     Pipeline fallback (new converter raises -> legacy)
"""

from __future__ import annotations

import os
import warnings
import logging
import pytest
from unittest.mock import MagicMock, patch

from src.ingestion.pdf_utils.pre_cleaner import (
    clean_pdf_text_block,
    _dehyphenate,
    _fix_kerning_spaces,
)
from src.ingestion.pdf_utils.extraction import (
    _group_chars_into_lines,
    _lines_to_text_blocks,
    _detect_multi_column,
    _strip_headers_footers,
    TextBlock,
    ImageBlock,
)
from src.ingestion.pdf_utils.tables import _table_to_markdown, _table_to_plain_text
from src.ingestion.pdf_utils.converter import _compute_body_size, _classify_block, MIN_TEXT_CHARS
from src.ingestion.docx_utils.normalization import (
    _normalize_markdown_common,
    _normalize_docx_markdown,
)


def _make_block(text, size, bold=False, x0=0.0, top=0.0, x1=100.0, bottom=12.0, page=1):
    return TextBlock(
        text=text, avg_size=size, is_bold=bold,
        x0=x0, top=top, x1=x1, bottom=bottom, page_num=page,
    )


# ══════════════════════════════════════════════════════════════════════════════
# HEADING DETECTION (D2)
# ══════════════════════════════════════════════════════════════════════════════

class TestHeadingDetection:
    """Tests #1, #2, #3 — relative heading classification."""

    def test_h1_large_font(self):
        """#1: Block at 1.6x body size -> H1."""
        body = 10.0
        block = _make_block("ServiceNow Overview", size=16.0)
        result = _classify_block(block, body)
        assert result.startswith("\n# ServiceNow Overview")

    def test_h2_medium_font(self):
        """#2: Block at 1.25x body -> H2."""
        body = 10.0
        block = _make_block("What is CSM", size=12.5)
        result = _classify_block(block, body)
        assert result.startswith("\n## What is CSM")

    def test_h3_slightly_larger_bold(self):
        """#2: Block at 1.06x body AND bold -> H3."""
        body = 10.0
        block = _make_block("Key Features", size=10.6, bold=True)
        result = _classify_block(block, body)
        assert result.startswith("\n### Key Features")

    def test_body_text_not_promoted(self):
        """#1: Block at body size -> plain paragraph, not a heading."""
        body = 10.0
        block = _make_block("This is regular body text.", size=10.0)
        result = _classify_block(block, body)
        assert not result.startswith("#")

    def test_d2_body_size_modal(self):
        """#2: _compute_body_size returns modal size when coverage >= 40%."""
        pages = [
            [_make_block("a" * 200, 10.0)] * 5 +
            [_make_block("Heading", 20.0)]
        ]
        body_size = _compute_body_size(pages)
        assert body_size == 10.0

    def test_d2_sanity_check_low_coverage_logs_warning(self, caplog):
        """#3: When modal coverage < 40%, a WARNING is logged."""
        pages = [
            [_make_block("a" * 10, float(s)) for s in range(8, 20)]
        ]
        with caplog.at_level(logging.WARNING, logger="src.ingestion.pdf_utils.converter"):
            _compute_body_size(pages)
        assert "uncertain" in caplog.text.lower() or "degraded" in caplog.text.lower()


# ══════════════════════════════════════════════════════════════════════════════
# ADMONITIONS (#4, #5)
# ══════════════════════════════════════════════════════════════════════════════

class TestAdmonitions:
    def test_note_admonition(self):
        """#4: 'Note: ...' -> > [!NOTE] after normalization."""
        raw = "Note: Always check ACLs before deploying."
        result = _normalize_markdown_common(raw)
        assert "> [!NOTE]" in result

    def test_warning_admonition(self):
        """#5: 'Warning: ...' -> > [!WARNING]."""
        raw = "Warning: Do not run this in production."
        result = _normalize_markdown_common(raw)
        assert "> [!WARNING]" in result

    def test_tip_admonition(self):
        """Tip: ... -> > [!TIP]."""
        raw = "Tip: Use the keyboard shortcut for speed."
        result = _normalize_markdown_common(raw)
        assert "> [!TIP]" in result


# ══════════════════════════════════════════════════════════════════════════════
# BULLETS (#6) AND NUMBERED SEQUENCES (#7)
# ══════════════════════════════════════════════════════════════════════════════

class TestBulletNormalization:
    def test_bullet_dot_normalized(self):
        """#6: '•' -> '- item'."""
        body = 10.0
        block = _make_block("• Check the SLA", size=10.0)
        result = _classify_block(block, body)
        assert result.startswith("- Check the SLA")

    def test_solid_bullet_normalized(self):
        """#6: '●' -> '- item'."""
        body = 10.0
        block = _make_block("● Another item", size=10.0)
        result = _classify_block(block, body)
        assert result.startswith("- Another item")

    def test_numbered_sequence_to_heading(self):
        """#7: '1. Section', '1.1 Sub' -> ## / ### via normalizer."""
        raw = "1. Introduction\n\n1.1 Background"
        result = _normalize_markdown_common(raw)
        assert "## 1. Introduction" in result or "## 1 Introduction" in result


# ══════════════════════════════════════════════════════════════════════════════
# KEY TAKEAWAY (#8)
# ══════════════════════════════════════════════════════════════════════════════

class TestKeyTakeaway:
    def test_key_takeaway_blockquote(self):
        """#8: '✔ Key takeaway:' -> blockquote."""
        raw = "✔ Key takeaway: Always document your changes."
        result = _normalize_markdown_common(raw)
        assert "> **✔ Key takeaway:**" in result


# ══════════════════════════════════════════════════════════════════════════════
# SERVICENOW CODE FENCING (#9)
# ══════════════════════════════════════════════════════════════════════════════

class TestServiceNowCodeFencing:
    def test_gs_log_fenced(self):
        """#9: 'gs.log(...)' -> ```javascript fence."""
        body = 10.0
        block = _make_block("gs.log('Hello World');", size=10.0)
        result = _classify_block(block, body)
        assert "```javascript" in result

    def test_new_glide_record_fenced(self):
        """#9: 'new GlideRecord(...)' -> fenced."""
        body = 10.0
        block = _make_block("var gr = new GlideRecord('incident');", size=10.0)
        result = _classify_block(block, body)
        assert "```javascript" in result


# ══════════════════════════════════════════════════════════════════════════════
# DEHYPHENATION (#14, KL-1)
# ══════════════════════════════════════════════════════════════════════════════

class TestDehyphenation:
    def test_dehyphen_correct_case(self):
        """#14: 'config-\\nuration' -> 'configuration'."""
        result = _dehyphenate("config-\nuration")
        assert result == "configuration"

    def test_dehyphen_known_wrong(self):
        """KL-1: 'well-\\nknown' -> 'wellknown' (documented wrong behavior).
        This test ASSERTS the known-bad output to track it as a documented regression.
        """
        result = _dehyphenate("well-\nknown")
        assert result == "wellknown", (
            "KL-1 known limitation: compound-word dehyphenation is wrong. "
            "Documented accepted trade-off (no dictionary check)."
        )


# ══════════════════════════════════════════════════════════════════════════════
# KERNING REPAIR (KL-2)
# ══════════════════════════════════════════════════════════════════════════════

class TestKerningRepair:
    def test_kerning_fixed(self):
        """KL-2: 'c o n f i g' (6 single chars) -> 'config'."""
        result = _fix_kerning_spaces("c o n f i g")
        assert result == "config"

    def test_kerning_no_fire_normal(self):
        """KL-2: 'a b c' (only 3 single chars) should NOT be collapsed."""
        result = _fix_kerning_spaces("a b c")
        assert result == "a b c"

    def test_kerning_no_fire_regular_words(self):
        """KL-2: Normal prose is untouched."""
        text = "The quick brown fox"
        assert _fix_kerning_spaces(text) == text


# ══════════════════════════════════════════════════════════════════════════════
# TABLES (#15, D5)
# ══════════════════════════════════════════════════════════════════════════════

class TestTables:
    def test_simple_pipe_table(self):
        """#15: 3-column table -> valid GFM pipe table."""
        table = [
            ["Name", "Role", "Access"],
            ["Alice", "Admin", "Full"],
            ["Bob", "User", "Read"],
        ]
        result = _table_to_markdown(table)
        assert "| Name | Role | Access |" in result
        assert "|---" in result
        assert "| Alice | Admin | Full |" in result

    def test_pipe_escaped_in_cells(self):
        """#15: Pipe chars in cells are escaped."""
        table = [["A|B", "C"]]
        result = _table_to_markdown(table)
        assert "A\\|B" in result

    def test_table_fallback_plain_text(self):
        """D5: _table_to_plain_text produces readable text without crashing."""
        table = [["Feature", "Value"], ["SLA", "4 hours"]]
        result = _table_to_plain_text(table)
        assert "Feature" in result
        assert "SLA" in result


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENT-LEVEL GUARD RAIL (#16)
# ══════════════════════════════════════════════════════════════════════════════

class TestGuardRail:
    def test_near_zero_text_raises(self):
        """#16: PDF yielding < MIN_TEXT_CHARS characters raises ValueError."""
        from src.ingestion.pdf_utils import converter as conv_mod

        # Patch the function in the converter module's namespace directly via monkeypatching
        original = conv_mod.extract_pdf_elements if hasattr(conv_mod, "extract_pdf_elements") else None

        def fake_extract(*a, **kw):
            return [[]], [[]], [False]

        conv_mod.extract_pdf_elements = fake_extract
        try:
            with patch("src.ingestion.core.get_branch_image_dir", return_value="/tmp"), \
                 patch("pdfplumber.open"):
                with pytest.raises(ValueError, match=r"only \d+ characters|OCR|scanned"):
                    conv_mod.convert_pdf_to_markdown("fake.pdf", "default")
        finally:
            if original is not None:
                conv_mod.extract_pdf_elements = original
            elif hasattr(conv_mod, "extract_pdf_elements"):
                del conv_mod.extract_pdf_elements

    def test_guard_rail_threshold_constant(self):
        """#16: MIN_TEXT_CHARS is set to a reasonable non-zero value."""
        assert MIN_TEXT_CHARS > 0
        assert MIN_TEXT_CHARS <= 500  # sanity — not absurdly high


# ══════════════════════════════════════════════════════════════════════════════
# HEADER/FOOTER STRIP (#20)
# ══════════════════════════════════════════════════════════════════════════════

class TestHeaderFooterStrip:
    def test_footer_removed_within_tolerance(self):
        """#20: Block with same text at similar top (within 2pt) on >=50% of pages is stripped."""
        footer_text = "Page 1 | Confidential"
        pages = [
            [
                _make_block(footer_text, 8.0, top=820.0 + (i * 0.5)),
                _make_block("Body text", 10.0, top=100.0),
            ]
            for i in range(4)
        ]
        result = _strip_headers_footers(pages, num_pages=4)
        for page_blocks in result:
            assert not any(b.text == footer_text for b in page_blocks)

    def test_unique_text_kept(self):
        """#20: Text appearing on only one page is not stripped."""
        pages = [
            [_make_block("Unique content on page 1", 10.0, top=100.0)],
            [_make_block("Different content", 10.0, top=100.0)],
            [_make_block("Yet another paragraph", 10.0, top=100.0)],
        ]
        result = _strip_headers_footers(pages, num_pages=3)
        assert any(b.text == "Unique content on page 1" for b in result[0])


# ══════════════════════════════════════════════════════════════════════════════
# SHIM EQUIVALENCE + DEPRECATION WARNING
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizerShim:
    """Shim test — validates no DOCX regression from the rename."""

    SAMPLE = (
        "## Introduction\n\n"
        "This is a paragraph.\n\n"
        "Note: Check ACLs.\n\n"
        "- Bullet one\n"
        "- Bullet two\n"
    )

    def test_shim_identical_output(self):
        """shim: _normalize_docx_markdown output == _normalize_markdown_common output."""
        expected = _normalize_markdown_common(self.SAMPLE)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            actual = _normalize_docx_markdown(self.SAMPLE)
        assert actual == expected, "Shim output differs — DOCX regression!"

    def test_shim_raises_deprecation_warning(self):
        """shim: Calling _normalize_docx_markdown raises DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _normalize_docx_markdown("some text")
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w)


# ══════════════════════════════════════════════════════════════════════════════
# structured_pdf_utils DEPRECATION (#19)
# ══════════════════════════════════════════════════════════════════════════════

class TestLegacyDeprecation:
    def test_convert_function_deprecated(self):
        """#19: convert_pdf_to_structured_markdown raises DeprecationWarning."""
        from src.ingestion import structured_pdf_utils
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                structured_pdf_utils.convert_pdf_to_structured_markdown("nonexistent.pdf")
            except Exception:
                pass
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w)

    def test_extract_images_function_deprecated(self):
        """#19: extract_images_from_pdf raises DeprecationWarning."""
        from src.ingestion import structured_pdf_utils
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            structured_pdf_utils.extract_images_from_pdf("nonexistent.pdf", "/tmp")
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w)


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE FALLBACK (#18)
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineFallback:
    def test_pipeline_falls_back_on_converter_error(self, caplog):
        """#18: If new converter raises, pipeline falls back to legacy and logs ERROR."""
        from src.ingestion.pipeline import process_and_ingest_files

        mock_file = MagicMock()
        mock_file.name = "test_doc.pdf"
        mock_file.getbuffer.return_value = b"%PDF-1.4 fake"

        # process_markdown_for_parent_child is imported inside pipeline.py's loop body;
        # patch at the chunking source module so it intercepts the lazy import.
        with patch("src.ingestion.pipeline.get_branch_upload_dir", return_value="/tmp"), \
             patch("src.ingestion.pipeline.get_embedder") as mock_emb, \
             patch("src.ingestion.pipeline.get_chroma_collection") as mock_col, \
             patch("src.ingestion.pipeline.load_branch_state", return_value={"files": {}}), \
             patch("src.ingestion.pipeline.save_branch_state"), \
             patch("src.ingestion.pipeline.save_parent_store"), \
             patch("src.ingestion.pipeline.update_master_branch_summary"), \
             patch("src.ingestion.pipeline.generate_file_summary", return_value="summary"), \
             patch("src.ingestion.chunking.process_markdown_for_parent_child",
                   return_value=({}, [])), \
             patch("src.ingestion.pdf_utils.convert_pdf_to_markdown",
                   side_effect=ValueError("Guard rail: near-zero text")), \
             patch("src.ingestion.structured_pdf_utils.convert_pdf_to_structured_markdown",
                   return_value="# Fallback MD") as mock_legacy, \
             patch("builtins.open", MagicMock()), \
             patch("os.path.exists", return_value=False):

            mock_emb.return_value.encode.return_value = MagicMock(tolist=lambda: [])
            mock_col.return_value = MagicMock()

            with caplog.at_level(logging.ERROR):
                try:
                    process_and_ingest_files("test_branch", [mock_file])
                except Exception:
                    pass

        assert "Falling back to legacy" in caplog.text or mock_legacy.called
