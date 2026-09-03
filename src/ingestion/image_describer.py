"""
src/ingestion/image_describer.py
================================
Image Describer Agent for multi-modal ingestion.
Takes an image (as base64) and returns a concise, semantic technical description.
Supports OpenRouter and local fallback.
"""

from __future__ import annotations

import base64
import logging
import requests
from abc import ABC, abstractmethod

from src.config import (
    VISION_LLM_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_VISION_MODEL,
    LOCAL_VISION_ENDPOINT,
)

logger = logging.getLogger(__name__)

# Fallback technical prompt for the vision model
SYSTEM_PROMPT = """
You are an expert AI vision assistant. Your task is to analyze the provided image and generate a concise, highly accurate description of its contents.
The description will be injected into a Markdown document as the image's substitute text, so it must capture all semantic meaning needed for a Retrieval-Augmented Generation (RAG) system.

Focus on:
1. Identifying the core subject, context, and key details.
2. Describing relationships or processes if it is a diagram or flowchart.
3. EXTRACTING ALL TEXT: If the image contains any readable text, labels, code snippets, or handwriting, you MUST transcribe it verbatim and include it in your description.

Keep it factual, structured, and avoid conversational filler (e.g., do not say 'This image shows...').
"""


class BaseVisionClient(ABC):
    @abstractmethod
    def describe_image(self, base64_data: str, mime_type: str = "image/png") -> str:
        """Get a semantic description of an image."""
        pass


class OpenRouterVisionClient(BaseVisionClient):
    def describe_image(self, base64_data: str, mime_type: str = "image/png") -> str:
        # Read at call-time so .env changes are always reflected
        import os
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
        model = os.environ.get("OPENROUTER_VISION_MODEL", "qwen/qwen3.8-flash")

        if not api_key:
            logger.warning("OPENROUTER_API_KEY is not set. Returning placeholder.")
            return "Image description unavailable (No API key)."

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://snowwiki.app",
            "X-Title": "SnowWiki",
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_data}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 300,
        }

        import time

        max_retries = 5
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=45,
                )
                if resp.status_code == 429:
                    wait = 5 * (2 ** attempt)  # 5s, 10s, 20s, 40s, 80s
                    logger.warning(f"Rate limited (429). Retrying in {wait}s... (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"Vision API error: {e}")
                while True:
                    user_input = input(f"Vision API error: {e}. Continue retrying? (y/n): ").strip().lower()
                    if user_input in ('y', 'n'):
                        break
                    print("Please enter 'y' or 'n'.")
                
                if user_input == 'n':
                    logger.info("User chose to skip processing for this image.")
                    return "Image description unavailable (skipped by user)."
                
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"OpenRouter vision API failed after {max_retries} attempts: {e}")
                    return "Image description unavailable due to an API error."
        
        return "Image description unavailable (rate limit exceeded)."


class LocalVisionClient(BaseVisionClient):
    def describe_image(self, base64_data: str, mime_type: str = "image/png") -> str:
        # Placeholder for local vision model API (e.g., Ollama with LLaVA)
        logger.info("Using LocalVisionClient placeholder.")
        return "Local vision description placeholder."


class ImageDescriberAgent:
    def __init__(self):
        if VISION_LLM_PROVIDER.lower() == "openrouter":
            self.client = OpenRouterVisionClient()
        else:
            self.client = LocalVisionClient()

    def describe_from_path(self, file_path: str) -> str:
        """Read image from path, convert to base64, and describe it."""
        try:
            with open(file_path, "rb") as f:
                img_data = f.read()
            b64 = base64.b64encode(img_data).decode("utf-8")
            
            # Basic mime type inference
            mime_type = "image/jpeg"
            if file_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif file_path.lower().endswith(".webp"):
                mime_type = "image/webp"

            return self.client.describe_image(b64, mime_type)
        except Exception as e:
            logger.error(f"Failed to read and describe image {file_path}: {e}")
            return "Image read error."
