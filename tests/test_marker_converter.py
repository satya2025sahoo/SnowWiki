"""
tests/test_marker_converter.py
==============================
Unit tests for the marker-pdf integration in pdf_utils:
- Singleton caching of PdfConverter
- Image extraction and markdown link path rewriting
- torch.cuda.OutOfMemoryError and exception handling
- Fallback from marker to secondary converters
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

import src.ingestion.pdf_utils.marker_converter as mc
from src.ingestion.pdf_utils.converter import convert_pdf_to_markdown


class TestMarkerConverter:

    def test_singleton_caching(self):
        """get_marker_converter initializes once and returns cached instance."""
        with patch.object(mc, "_CONVERTER", None), \
             patch.object(mc, "_MODEL_DICT", None), \
             patch("marker.models.create_model_dict", return_value={"mock": "model"}) as mock_models, \
             patch("marker.converters.pdf.PdfConverter") as mock_converter_cls:

            instance1 = mc.get_marker_converter()
            instance2 = mc.get_marker_converter()

            assert instance1 is instance2
            mock_models.assert_called_once()
            mock_converter_cls.assert_called_once_with(artifact_dict={"mock": "model"})

    def test_convert_pdf_with_marker_saves_images_and_rewrites_links(self, tmp_path):
        """Extracted PIL images are saved to image_dir and image links in markdown are updated."""
        fake_pdf = str(tmp_path / "sample.pdf")
        with open(fake_pdf, "wb") as f:
            f.write(b"%PDF-1.4")

        img_dir = str(tmp_path / "images")
        dummy_img = Image.new("RGB", (10, 10), color="blue")
        images_dict = {"figure_1.png": dummy_img}
        raw_markdown = "# Sample Title\n\nHere is a diagram: ![](figure_1.png)\nAnd detailed explanation."

        with patch("src.ingestion.pdf_utils.marker_converter.convert_with_marker",
                   return_value=(raw_markdown, images_dict, {})):
            result_md = mc.convert_pdf_with_marker(
                file_path=fake_pdf,
                image_dir=img_dir,
                image_rel_prefix="images/",
            )

            # Link was rewritten to images/figure_1.png
            assert "![](images/figure_1.png)" in result_md
            # File was saved to disk
            saved_img = os.path.join(img_dir, "figure_1.png")
            assert os.path.exists(saved_img)

    def test_convert_pdf_with_marker_empty_text_raises(self, tmp_path):
        """If marker extracts near-zero or empty text, ValueError is raised."""
        fake_pdf = str(tmp_path / "empty.pdf")
        with patch("src.ingestion.pdf_utils.marker_converter.convert_with_marker",
                   return_value=("   ", {}, {})):
            with pytest.raises(ValueError, match="Marker extracted empty text"):
                mc.convert_pdf_with_marker(fake_pdf, str(tmp_path / "images"))

    def test_convert_pdf_with_marker_cuda_oom(self, tmp_path):
        """CUDA OOM error is logged and re-raised so fallback catches it."""
        import torch
        fake_pdf = str(tmp_path / "oom.pdf")

        with patch("src.ingestion.pdf_utils.marker_converter.convert_with_marker",
                   side_effect=torch.cuda.OutOfMemoryError("CUDA out of memory")):
            with pytest.raises(torch.cuda.OutOfMemoryError):
                mc.convert_pdf_with_marker(fake_pdf, str(tmp_path / "images"))

    def test_convert_pdf_to_markdown_uses_marker_primary(self, tmp_path):
        """convert_pdf_to_markdown uses marker-pdf when available."""
        fake_pdf = str(tmp_path / "test.pdf")
        with open(fake_pdf, "wb") as f:
            f.write(b"%PDF-1.4")

        long_marker_md = "# Marker Generated Heading\n\n" + ("This is detailed text from Marker. " * 10)

        with patch("src.ingestion.pdf_utils.marker_converter.convert_pdf_with_marker",
                   return_value=long_marker_md) as mock_marker, \
             patch("pymupdf4llm.to_markdown") as mock_pymupdf:

            output = convert_pdf_to_markdown(fake_pdf, branch_name="test_branch", image_dir=str(tmp_path))

            mock_marker.assert_called_once()
            mock_pymupdf.assert_not_called()
            assert "Marker Generated Heading" in output

    def test_convert_pdf_to_markdown_falls_back_when_marker_fails(self, tmp_path):
        """When marker fails, convert_pdf_to_markdown gracefully falls back to pymupdf4llm."""
        fake_pdf = str(tmp_path / "fallback.pdf")
        with open(fake_pdf, "wb") as f:
            f.write(b"%PDF-1.4")

        pymupdf_md = "# PyMuPDF Heading\n\n" + ("Extracted via pymupdf fallback. " * 10)

        with patch("src.ingestion.pdf_utils.marker_converter.convert_pdf_with_marker",
                   side_effect=RuntimeError("Marker model load failure")), \
             patch("pymupdf4llm.to_markdown", return_value=pymupdf_md) as mock_pymupdf:

            output = convert_pdf_to_markdown(fake_pdf, branch_name="test_branch", image_dir=str(tmp_path))

            mock_pymupdf.assert_called_once()
            assert "PyMuPDF Heading" in output
