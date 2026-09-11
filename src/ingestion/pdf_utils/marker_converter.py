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

# Force CPU-safe backend for surya-ocr (default=transformers, no Docker required).
# Can be overridden to 'llama.cpp' or 'vllm' via the env var if GPU is available.
# 'vllm' requires Docker; 'transformers' runs natively on CPU/GPU without Docker.
os.environ.setdefault("SURYA_INFERENCE_BACKEND", "transformers")
os.environ.setdefault("TORCH_DEVICE", "cpu")

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
        _CONVERTER = PdfConverter(artifact_dict=_MODEL_DICT)
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
