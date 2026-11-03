"""
src/ingestion/image_describer.py
================================
Image Describer Agent for multi-modal ingestion.
Supports Qwen-VL (via OpenRouter) and Local fallback.

Specialized for:
  - Flowcharts & Process Diagrams  -> step-by-step sequences
  - Tables & Data Grids            -> GitHub-Flavored Markdown tables
  - Graphs & Charts                -> axes, legends, key metrics
  - ServiceNow UI / Forms          -> field names, module paths, values
  - General OCR                    -> verbatim text extraction

Debug logging:
  Every extraction is appended to vision_debug.json in the image directory
  so you can inspect exactly what Qwen-VL saw and extracted.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime

import requests

from src.config import VISION_LLM_PROVIDER, LOCAL_VISION_MODEL

logger = logging.getLogger(__name__)

# ── Qwen-VL System Prompt ──────────────────────────────────────────────────────
QWEN_SYSTEM_PROMPT = """You are an expert AI vision assistant specializing in technical documentation.
Analyze the provided image and produce a highly accurate, structured description.
The description will be embedded into a Markdown document for a RAG (Retrieval-Augmented Generation) system,
so it must capture ALL semantic meaning and searchable details.

CRITICAL RULES — Follow ALL of them:

1. FLOWCHARTS & PROCESS DIAGRAMS:
   - Trace each step in order with arrows: Step A -> Decision B -> Step C -> End
   - Label every decision diamond: e.g., [Decision: Is CI found in CMDB?] Yes -> ... / No -> ...
   - Identify start/end nodes and all branches.

2. TABLES & DATA GRIDS:
   - Convert DIRECTLY to GitHub-Flavored Markdown table syntax: | Col1 | Col2 | Col3 |
   - Preserve ALL headers and ALL rows exactly. Do not summarize or omit rows.
   - Maintain parent-child or grouped row relationships.

3. GRAPHS & CHARTS:
   - State the chart type (bar, line, pie, scatter, etc.)
   - Extract X-axis label, Y-axis label, unit of measurement, and legend entries.
   - Describe key trends, peaks, or values.

4. SERVICENOW UI / FORMS / SCREENSHOTS:
   - Extract module navigation path (e.g., Discovery > Schedules > New)
   - List every visible field name and its selected/entered value.
   - Transcribe all button labels, tab names, and related list column headers.

5. GENERAL OCR (All other images):
   - Transcribe ALL readable text verbatim, including labels, annotations, legends.
   - Preserve numbering, indentation, and bullet structure.

OUTPUT FORMAT:
- Start with one line: [Type: Flowchart | Table | Graph | UI Screenshot | Diagram | Other]
- Then provide the full structured extraction below.
- Do NOT say "This image shows..." or include conversational filler.
- Be factual, dense, and structured.
"""


# ── Base Client ────────────────────────────────────────────────────────────────

class BaseVisionClient(ABC):
    @abstractmethod
    def describe_image(self, base64_data: str, mime_type: str = "image/png", ocr_text: str = "") -> str:
        """Get a semantic description of an image."""
        pass


# ── Qwen-VL via OpenRouter ─────────────────────────────────────────────────────

class QwenVLClient(BaseVisionClient):
    """
    Calls Qwen-2.5-VL-72B-Instruct via OpenRouter for multi-modal image analysis.
    Configured from .env: OPENROUTER_API_KEY, OPENROUTER_VISION_MODEL.
    """

    def describe_image(self, base64_data: str, mime_type: str = "image/png", ocr_text: str = "") -> str:
        api_key  = os.environ.get("OPENROUTER_API_KEY", "")
        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
        model    = os.environ.get("OPENROUTER_VISION_MODEL", "qwen/qwen2.5-vl-72b-instruct")

        if not api_key:
            logger.warning("OPENROUTER_API_KEY not set — returning placeholder.")
            return "[Image description unavailable: No API key configured]"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://snowwiki.app",
            "X-Title":       "SnowWiki",
        }

        prompt = QWEN_SYSTEM_PROMPT
        if ocr_text:
            prompt += f"\n\n### OCR TEXT EXTRACTED FROM IMAGE ###\n{ocr_text}\n"

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_data}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 1500,
            "temperature": 0.1,
        }

        max_retries = 5
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90,
                )

                if resp.status_code == 429:
                    wait = 10 * (2 ** attempt)  # 10s, 20s, 40s, 80s, 160s
                    logger.warning(
                        "Qwen-VL rate limited (429). Waiting %ds (attempt %d/%d)...",
                        wait, attempt + 1, max_retries,
                    )
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()

            except requests.HTTPError as e:
                logger.error("Qwen-VL HTTP error: %s — %s", e, resp.text[:300])
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return f"[Image description unavailable: HTTP error {e}]"
            except Exception as e:
                logger.error("Qwen-VL unexpected error: %s", e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return f"[Image description unavailable: {e}]"

        return "[Image description unavailable: rate limit exceeded]"


# ── Groq Vision Client (Llama 3.2 Vision) ─────────────────────────────────────

class GroqVisionClient(BaseVisionClient):
    """
    Calls Llama 3.2 Vision via Groq for multi-modal image analysis.
    Configured from .env: GROQ_API_KEY. Uses llama-3.2-11b-vision-preview for low cost.
    """

    def describe_image(self, base64_data: str, mime_type: str = "image/png", ocr_text: str = "") -> str:
        api_key  = os.environ.get("GROQ_API_KEY", "")
        base_url = "https://api.groq.com/openai/v1"
        model    = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

        if not api_key:
            logger.warning("GROQ_API_KEY not set — returning placeholder.")
            return "[Image description unavailable: No API key configured]"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        }

        prompt = QWEN_SYSTEM_PROMPT
        if ocr_text:
            prompt += f"\n\n### OCR TEXT EXTRACTED FROM IMAGE ###\n{ocr_text}\n"

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_data}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 1500,
            "temperature": 0.1,
        }

        max_retries = 5
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90,
                )

                if resp.status_code == 429:
                    wait = 10 * (2 ** attempt)
                    logger.warning(
                        "Groq rate limited (429). Waiting %ds (attempt %d/%d)...",
                        wait, attempt + 1, max_retries,
                    )
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()

            except requests.HTTPError as e:
                logger.error("Groq HTTP error: %s — %s", e, resp.text[:300])
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return f"[Image description unavailable: HTTP error {e}]"
            except Exception as e:
                logger.error("Groq unexpected error: %s", e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return f"[Image description unavailable: {e}]"

        return "[Image description unavailable: rate limit exceeded]"


# ── Local Vision Client (Ollama / LLaVA) ──────────────────────────────────────

class LocalVisionClient(BaseVisionClient):
    """
    Calls a local vision model via an OpenAI-compatible endpoint.
    Set LOCAL_VISION_ENDPOINT and LOCAL_VISION_MODEL in .env.
    """

    def describe_image(self, base64_data: str, mime_type: str = "image/png", ocr_text: str = "") -> str:
        endpoint = os.environ.get("LOCAL_VISION_ENDPOINT", "http://127.0.0.1:11434/v1")
        model    = os.environ.get("LOCAL_VISION_MODEL", "qwen3-vl:8b")
        base_url = endpoint.rstrip("/")

        prompt = QWEN_SYSTEM_PROMPT
        if ocr_text:
            prompt += f"\n\n### OCR TEXT EXTRACTED FROM IMAGE ###\n{ocr_text}\n"

        if base_url.endswith("/v1"):
            openai_url = f"{base_url}/chat/completions"
            ollama_url = f"{base_url[:-3]}/api/chat"
        else:
            openai_url = f"{base_url}/v1/chat/completions"
            ollama_url = f"{base_url}/api/chat"

        # Try 1: OpenAI-compatible endpoint
        payload_openai = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_data}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 1500,
        }

        try:
            resp = requests.post(openai_url, json=payload_openai, timeout=120)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

        # Try 2: Native Ollama /api/chat fallback
        try:
            payload_ollama = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [base64_data],
                    }
                ],
                "stream": False,
            }
            resp2 = requests.post(ollama_url, json=payload_ollama, timeout=120)
            if resp2.status_code == 200:
                data2 = resp2.json()
                return data2.get("message", {}).get("content", "").strip()
            resp2.raise_for_status()
        except Exception as e:
            logger.error("LocalVisionClient error: %s", e)
            return f"[Local vision model error: {e}]"

        return "[Local vision model returned empty response]"


# ── Debug Logger ───────────────────────────────────────────────────────────────

class VisionDebugLogger:
    """
    Persists each Qwen-VL extraction result to vision_debug.json
    inside the image directory for full transparency and debugging.
    """

    def __init__(self, image_dir: str, document_name: str, branch_name: str, vlm_model: str):
        self.debug_path    = os.path.join(image_dir, "vision_debug.json")
        self.document_name = document_name
        self.branch_name   = branch_name
        self.vlm_model     = vlm_model

    def _load(self) -> dict:
        if os.path.exists(self.debug_path):
            try:
                with open(self.debug_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "document":     self.document_name,
            "branch":       self.branch_name,
            "vlm_model":    self.vlm_model,
            "total_images": 0,
            "extractions":  [],
        }

    def log(
        self,
        image_index:  int,
        filename:     str,
        full_path:    str,
        rel_path:     str,
        raw_vlm_output: str,
    ) -> None:
        """Append one extraction record and save debug JSON."""
        data = self._load()

        # Classify the image type from the first line Qwen emits
        first_line  = raw_vlm_output.split("\n")[0] if raw_vlm_output else ""
        image_type  = "Unknown"
        if "[Type:" in first_line:
            image_type = first_line.strip().lstrip("[").rstrip("]").replace("Type:", "").strip()

        record = {
            "image_index":         image_index,
            "filename":            filename,
            "relative_path":       rel_path,
            "full_path":           full_path,
            "image_classification": image_type,
            "raw_vlm_output":      raw_vlm_output,
            "timestamp":           datetime.now().isoformat(timespec="seconds"),
        }

        # Deduplicate by filename — update if already present
        existing = [e for e in data["extractions"] if e["filename"] != filename]
        existing.append(record)
        data["extractions"]  = existing
        data["total_images"] = len(existing)

        try:
            with open(self.debug_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("VisionDebugLogger: saved entry for %s", filename)
        except Exception as e:
            logger.error("VisionDebugLogger: failed to write debug file: %s", e)

    def is_cached(self, filename: str) -> bool:
        """Return True if this image already has a non-error entry in the debug log."""
        data = self._load()
        for entry in data.get("extractions", []):
            if entry["filename"] == filename:
                raw = entry.get("raw_vlm_output", "")
                if raw and "unavailable" not in raw.lower() and "error" not in raw.lower():
                    return True
        return False

    def get_cached_description(self, filename: str) -> str | None:
        """Return the cached VLM output for filename, or None."""
        data = self._load()
        for entry in data.get("extractions", []):
            if entry["filename"] == filename:
                return entry.get("raw_vlm_output")
        return None


# ── Main Agent ─────────────────────────────────────────────────────────────────

class ImageDescriberAgent:
    """
    Orchestrates Qwen-VL image description with debug logging and caching.

    Usage:
        agent = ImageDescriberAgent(image_dir="...", document_name="...", branch_name="...")
        description = agent.describe_from_path("path/to/image.png", image_index=1)
    """

    def __init__(
        self,
        image_dir:     str  = "",
        document_name: str  = "unknown",
        branch_name:   str  = "default",
    ):
        provider = (VISION_LLM_PROVIDER or os.environ.get("VISION_LLM_PROVIDER", "local")).lower()

        if provider == "local":
            self.client = LocalVisionClient()
            vlm_model   = LOCAL_VISION_MODEL or os.environ.get("LOCAL_VISION_MODEL", "qwen3-vl:8b")
        elif provider == "openrouter":
            self.client = QwenVLClient()
            vlm_model   = os.environ.get("OPENROUTER_VISION_MODEL", "qwen/qwen2.5-vl-72b-instruct")
        else:
            # Default to Groq Qwen Vision
            self.client = GroqVisionClient()
            vlm_model   = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

        self.image_dir = image_dir
        self.debug_logger = VisionDebugLogger(
            image_dir     = image_dir,
            document_name = document_name,
            branch_name   = branch_name,
            vlm_model     = vlm_model,
        ) if image_dir else None

    def describe_from_path(
        self,
        file_path:   str,
        image_index: int = 0,
        rel_path:    str = "",
        ocr_text:    str = "",
    ) -> str:
        """
        Read image from disk, send to Qwen-VL, log the result, and return the description.

        Args:
            file_path:   Absolute path to the saved image file.
            image_index: Sequential index within this document (for debug log ordering).
            rel_path:    Relative path as it will appear in the Markdown tag (e.g. 'images/img_1.png').

        Returns:
            The Qwen-VL description string (used as alt-text in the Markdown image tag).
        """
        filename = os.path.basename(file_path)

        # ── Cache check: skip re-billing if already extracted ──────────────────
        if self.debug_logger and self.debug_logger.is_cached(filename):
            cached = self.debug_logger.get_cached_description(filename)
            if cached:
                logger.info("VLM cache hit for %s — skipping API call.", filename)
                return cached

        # ── Read & encode ──────────────────────────────────────────────────────
        try:
            with open(file_path, "rb") as f:
                img_bytes = f.read()
        except Exception as e:
            logger.error("Cannot read image file %s: %s", file_path, e)
            return f"[Image read error: {e}]"

        b64 = base64.b64encode(img_bytes).decode("utf-8")

        # ── MIME type ──────────────────────────────────────────────────────────
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png",  ".gif":  "image/gif",
                    ".webp": "image/webp", ".bmp": "image/bmp"}
        mime_type = mime_map.get(ext, "image/png")

        # ── Call VLM ──────────────────────────────────────────────────────────
        logger.info("Calling Qwen-VL for image: %s (index %d)", filename, image_index)
        description = self.client.describe_image(b64, mime_type)

        # ── Log to debug file ──────────────────────────────────────────────────
        if self.debug_logger:
            self.debug_logger.log(
                image_index    = image_index,
                filename       = filename,
                full_path      = file_path,
                rel_path       = rel_path or f"images/{filename}",
                raw_vlm_output = description,
            )

        return description

    def sanitize_alt_text(self, description: str) -> str:
        """
        Sanitize description for use as Markdown alt-text.
        Truncates to 400 chars, removes bracket characters that break Markdown parsing.
        """
        text = description.replace("\n", " ").replace("\r", " ")
        text = text.replace("[", "(").replace("]", ")")
        # Collapse extra whitespace
        import re
        text = re.sub(r"\s+", " ", text).strip()
        return text[:400]
