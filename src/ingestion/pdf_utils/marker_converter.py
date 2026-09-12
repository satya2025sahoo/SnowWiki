"""
src/ingestion/pdf_utils/marker_converter.py
============================================
Marker-based PDF -> Markdown converter using datalab-to/marker.

Provides:
- Singleton / cached model loading to avoid redundant initialization overhead.
- Graceful error handling including torch.cuda.OutOfMemoryError and Windows path safety.
- PIL Image extraction and saving to target directory with link normalization.
- Configurable torch device via TORCH_DEVICE env var.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Tuple

# Windows & Hugging Face stability optimizations
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

# Force CPU-safe backend for surya-ocr — llamacpp uses llama-server binary,
# no Docker or NVIDIA GPU required. Overridable via environment.
os.environ.setdefault("SURYA_INFERENCE_BACKEND", "llamacpp")
os.environ.setdefault("TORCH_DEVICE", "cuda")  # GPU — falls back to cpu if no CUDA

# Offload all llama-server layers to GPU (set 0 to force CPU)
os.environ.setdefault("LLAMA_CPP_NGL", "99")

# Point surya to the bundled llama-server binary if not already set in env
_DEFAULT_LLAMA_SERVER = os.path.join(
    os.path.dirname(__file__),        # .../pdf_utils/
    "..", "..", "..",                  # up to d:\SnowWiki
    "tools", "llama-cpp", "llama-server.exe",
)
os.environ.setdefault(
    "LLAMA_CPP_BINARY",
    os.path.normpath(_DEFAULT_LLAMA_SERVER),
)

# Point surya to local GGUF models if present (avoids HuggingFace download)
_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
os.environ.setdefault(
    "SURYA_GGUF_LOCAL_MODEL_PATH",
    os.path.join(_REPO_ROOT, "models", "surya-2.gguf"),
)
os.environ.setdefault(
    "SURYA_GGUF_LOCAL_MMPROJ_PATH",
    os.path.join(_REPO_ROOT, "models", "surya-2-mmproj.gguf"),
)

logger = logging.getLogger(__name__)

_MODEL_DICT: dict | None = None
_CONVERTER: Any = None


def get_marker_converter():
    """
    Lazy-load and cache the Marker PdfConverter and model dictionary singleton.
    """
    global _MODEL_DICT, _CONVERTER
    if _CONVERTER is None:
        logger.info("Initializing Marker model dictionary and PdfConverter...")
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        device = os.environ.get("TORCH_DEVICE", None)
        if device:
            logger.info("Configuring Marker with TORCH_DEVICE: %s", device)

        _MODEL_DICT = create_model_dict()
        
        # Windows multiprocessing fails inside pdftext unless strictly guarded,
        # but Streamlit runs are already threaded. We must force pdftext_workers=1
        # to disable multiprocessing inside the PDF parsing stage.
        _CONVERTER = PdfConverter(
            artifact_dict=_MODEL_DICT,
            config={"pdftext_workers": 1}
        )
        logger.info("Marker converter successfully initialized.")
    return _CONVERTER


def convert_with_marker(pdf_path: str) -> Tuple[str, dict[str, Any], Any]:
    """
    Direct low-level invocation of Marker.
    Returns (text, images, metadata).
    """
    converter = get_marker_converter()
    rendered = converter(pdf_path)

    from marker.output import text_from_rendered
    text, metadata, images = text_from_rendered(rendered)
    return text, images, metadata


def convert_pdf_with_marker(
    file_path: str,
    image_dir: str,
    image_rel_prefix: str = "images/",
) -> str:
    """
    High-level conversion function for SnowWiki pipeline.
    
    Converts PDF using marker, saves any extracted PIL images to `image_dir`,
    and normalizes image references in the Markdown to `image_rel_prefix`.
    
    Raises:
        Exception: If marker conversion fails (caller handles fallback).
    """
    import torch

    try:
        text, images, metadata = convert_with_marker(file_path)
    except torch.cuda.OutOfMemoryError as oom:
        logger.error(
            "CUDA Out-Of-Memory encountered while converting '%s' with Marker: %s. Triggering fallback.",
            file_path,
            oom,
        )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise
    except Exception as e:
        logger.error(
            "Marker conversion failed for '%s': %s. Triggering fallback.",
            file_path,
            e,
        )
        raise

    if not text or not text.strip():
        raise ValueError(f"Marker extracted empty text from {file_path}")

    # Ensure image directory exists if images were extracted
    if images:
        os.makedirs(image_dir, exist_ok=True)
        for img_name, img_obj in images.items():
            img_save_path = os.path.join(image_dir, img_name)
            try:
                img_obj.save(img_save_path)
                logger.debug("Saved extracted image: %s", img_save_path)
            except Exception as e:
                logger.warning("Could not save image '%s': %s", img_name, e)

            # Ensure markdown image links match the relative prefix (e.g. images/<name>)
            # Marker outputs ![](img_name) or ![...](img_name)
            escaped_name = re.escape(img_name)
            # If the text has `(img_name)`, replace with `(images/img_name)`
            text = re.sub(
                rf"\((?:[^\)\s]*/)?{escaped_name}\)",
                f"({image_rel_prefix.rstrip('/')}/{img_name})",
                text,
            )

    return text
