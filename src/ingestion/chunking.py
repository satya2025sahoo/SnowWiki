"""
src/ingestion/chunking.py
=========================
Chunking algorithms for the SnowWiki ingestion pipeline.

Covers:
  - extract_document_text        : raw text from PDF, DOCX, TXT
  - segment_into_parent_sections : LLM-based semantic topic segmentation
  - split_into_children          : overlapping ~200-word child chunks per parent
  - parse_transcript_chunks      : timestamp-aware chunking of Whisper transcripts
  - chunk_document_text          : paragraph-based chunking for documents (legacy)
  - process_markdown_for_parent_child : structured markdown → parent+child dicts

DOCX → Markdown conversion has been moved to src/ingestion/docx_utils.py.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid

logger = logging.getLogger(__name__)

from pypdf import PdfReader
from docx import Document

from src.ingestion.core import parse_timestamp_str


# ── Text Extraction ────────────────────────────────────────────────────────────

def extract_document_text(file_path: str, file_ext: str) -> str:
    """Extract raw text from a PDF, DOCX, or TXT file."""
    ext  = file_ext.lower()
    text = ""

    if ext == ".pdf":
        reader     = PdfReader(file_path)
        pages_text = [page.extract_text() for page in reader.pages if page.extract_text()]
        text       = "\n\n".join(pages_text)

    elif ext == ".docx":
        doc        = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text       = "\n\n".join(paragraphs)

    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    return text


# ── Semantic Parent-Child Chunking ─────────────────────────────────────────────

def _parse_llm_json(raw_response: str, filename: str) -> list[dict]:
    """
    Extract a JSON array of topic sections from the LLM's raw response.

    Guardrail strategy:
    1. Try to extract a ```json ... ``` fenced block via regex.
    2. Attempt a bare json.loads on the whole response.
    3. Fallback: split text into ~2 000-char sections manually.
    """
    # 1. Fenced block extraction
    match = re.search(r"```json\s*(.*?)\s*```", raw_response, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, list) and data:
                return data
        except json.JSONDecodeError:
            pass

    # 2. Bare JSON parse
    try:
        data = json.loads(raw_response.strip())
        if isinstance(data, list) and data:
            return data
    except json.JSONDecodeError:
        pass

    # 3. Manual fallback — paragraph chunking at ~2 000 chars
    print(f"[ingestion] LLM JSON parse failed for '{filename}', falling back to paragraph split.")
    paragraphs = [p.strip() for p in raw_response.split("\n\n") if p.strip()]
    sections: list[dict] = []
    buf = ""
    i = 0
    for para in paragraphs:
        if len(buf) + len(para) < 2000:
            buf = f"{buf}\n\n{para}".strip()
        else:
            if buf:
                i += 1
                sections.append({"topic_title": f"Section {i}", "content": buf})
            buf = para
    if buf:
        i += 1
        sections.append({"topic_title": f"Section {i}", "content": buf})
    return sections if sections else [{"topic_title": "Section 1", "content": raw_response}]


def segment_into_parent_sections(text: str, filename: str, source: str) -> list[dict]:
    """
    Partition raw text into semantically coherent Parent Sections using an LLM.

    For long texts (> 12 000 chars) the input is split into overlapping 10 000-char
    windows before calling the LLM, and results are merged.

    Returns:
        List of parent section dicts with parent_id, topic_title, content, source.
    """
    if not text or not text.strip():
        return []

    # Very short text — skip LLM, treat whole text as one parent
    if len(text.strip()) < 600:
        return [{
            "parent_id":   str(uuid.uuid4()),
            "topic_title": f"{filename} — Full Content",
            "content":     text.strip(),
            "source":      source,
        }]

    SEGMENTATION_PROMPT = (
        "You are a technical document analyst specialising in ServiceNow training content.\n"
        "Your task: Segment the following text into logical topic sections based on SEMANTIC MEANING.\n\n"
        "Rules:\n"
        "1. Each section must be between 500 and 2,500 characters.\n"
        "2. If a single topic is longer than 2,500 characters, split it into 'Sub-topic Part 1', 'Sub-topic Part 2', etc.\n"
        "3. Use clear, descriptive topic_title strings (e.g., 'CMDB Class Constraints Overview').\n"
        "4. Output STRICTLY valid JSON wrapped in ```json ... ``` — no extra text outside the block.\n\n"
        "Output format:\n"
        "```json\n"
        "[\n"
        "  {\"topic_title\": \"Topic Name Here\", \"content\": \"Full section text here...\"},\n"
        "  ...\n"
        "]\n"
        "```\n\n"
        "TEXT TO SEGMENT:\n"
    )

    # Build windows for long texts
    WINDOW_SIZE   = 10_000
    WINDOW_STRIDE = 9_000
    if len(text) > 12_000:
        windows = [
            text[i: i + WINDOW_SIZE]
            for i in range(0, len(text), WINDOW_STRIDE)
            if text[i: i + WINDOW_SIZE].strip()
        ]
    else:
        windows = [text]

    raw_sections: list[dict] = []

    try:
        from src.llm_wrapper import get_chat_client
        from src.config import GROQ_CLASSIFIER_MODEL
        client = get_chat_client()

        for window in windows:
            response = client.chat.completions.create(
                model=GROQ_CLASSIFIER_MODEL,
                messages=[{
                    "role": "user",
                    "content": SEGMENTATION_PROMPT + window
                }],
                max_tokens=2048,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            parsed = _parse_llm_json(raw, filename)
            raw_sections.extend(parsed)

    except Exception as exc:
        print(f"[ingestion] Segmentation LLM error for '{filename}': {exc}")
        raw_sections = [{"topic_title": f"{filename} — Full Content", "content": text}]

    # Assign UUIDs and source to every section
    parent_sections: list[dict] = []
    for sec in raw_sections:
        content = str(sec.get("content", "")).strip()
        if not content:
            continue
        parent_sections.append({
            "parent_id":   str(uuid.uuid4()),
            "topic_title": str(sec.get("topic_title", "Untitled Section")).strip(),
            "content":     content,
            "source":      source,
        })

    return parent_sections


def split_into_children(parent_section: dict) -> list[dict]:
    """
    Slice a Parent Section into overlapping ~200-word Child Chunks (30-word overlap).

    Each child inherits parent_id, topic_title, and source.
    """
    content     = parent_section.get("content", "")
    parent_id   = parent_section.get("parent_id")
    topic_title = parent_section.get("topic_title", "")
    source      = parent_section.get("source", "")

    if not parent_id:
        parent_id = f"parent_fallback_{uuid.uuid4().hex[:8]}"
        logger.warning(
            "split_into_children: parent section missing 'parent_id'. Assigned fallback: %s",
            parent_id,
        )

    words = content.split()
    if not words:
        return []

    CHUNK_WORDS   = 200
    OVERLAP_WORDS = 30

    children: list[dict] = []
    start = 0
    while start < len(words):
        end       = min(start + CHUNK_WORDS, len(words))
        chunk_txt = " ".join(words[start:end])
        children.append({
            "parent_id":   parent_id,
            "topic_title": topic_title,
            "source":      source,
            "chunk_text":  chunk_txt,
        })
        if end == len(words):
            break
        start += CHUNK_WORDS - OVERLAP_WORDS

    return children


# ── Transcript Chunking ────────────────────────────────────────────────────────

def parse_transcript_chunks(
    transcript_text: str,
    filename: str,
    branch_name: str,
    media_path: str,
) -> list[dict]:
    """
    Parse Groq Whisper timestamped transcript lines into chunk dicts.
    Lines are expected in the format: [MM:SS] Text content.
    Falls back to paragraph chunking if no timestamps are detected.
    """
    pattern = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)$")
    lines   = transcript_text.splitlines()

    chunks: list[dict]    = []
    current_time_str = "00:00"
    current_seconds  = 0
    current_buf: list[str] = []

    def _flush_buf() -> None:
        buf_text = " ".join(current_buf).strip()
        if buf_text:
            chunks.append(
                {
                    "text":              f"[{current_time_str}] {buf_text}",
                    "timestamp":         current_time_str,
                    "timestamp_seconds": current_seconds,
                    "branch":            branch_name,
                    "source_file":       filename,
                    "media_path":        media_path,
                    "type":              "media",
                }
            )

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue

        match = pattern.match(line_str)
        if match:
            _flush_buf()
            current_buf      = []
            current_time_str = match.group(1)
            current_seconds  = parse_timestamp_str(current_time_str)
            text_part        = match.group(2)
            if text_part:
                current_buf.append(text_part)
        else:
            current_buf.append(line_str)

    _flush_buf()

    # Paragraph fallback when no timestamps were found
    if not chunks and transcript_text.strip():
        for para in [p.strip() for p in transcript_text.split("\n\n") if p.strip()]:
            chunks.append(
                {
                    "text":              para,
                    "timestamp":         "00:00",
                    "timestamp_seconds": 0,
                    "branch":            branch_name,
                    "source_file":       filename,
                    "media_path":        media_path,
                    "type":              "media",
                }
            )

    return chunks


# ── Document Paragraph Chunking (legacy) ──────────────────────────────────────

def chunk_document_text(
    doc_text: str,
    filename: str,
    branch_name: str,
    file_path: str = "",
    file_ext: str = "",
) -> list[dict]:
    """Chunk raw document text by paragraphs (target ~800 chars per chunk) with PDF page tracking."""
    chunks: list[dict] = []
    ext = file_ext.lower()

    if ext == ".pdf" and file_path and os.path.exists(file_path):
        try:
            reader = PdfReader(file_path)
            for page_num, page in enumerate(reader.pages, start=1):
                p_text = page.extract_text()
                if not p_text or not p_text.strip():
                    continue
                paragraphs = [p.strip() for p in p_text.split("\n\n") if p.strip()]
                buf = ""
                for para in paragraphs:
                    if len(buf) + len(para) < 800:
                        buf = f"{buf}\n\n{para}".strip()
                    else:
                        if buf:
                            chunks.append(
                                {
                                    "text":              buf,
                                    "timestamp":         "N/A",
                                    "timestamp_seconds": 0,
                                    "page":              page_num,
                                    "branch":            branch_name,
                                    "source_file":       filename,
                                    "media_path":        "",
                                    "type":              "document",
                                }
                            )
                        buf = para
                if buf:
                    chunks.append(
                        {
                            "text":              buf,
                            "timestamp":         "N/A",
                            "timestamp_seconds": 0,
                            "page":              page_num,
                            "branch":            branch_name,
                            "source_file":       filename,
                            "media_path":        "",
                            "type":              "document",
                        }
                    )
            if chunks:
                return chunks
        except Exception as exc:
            print(f"[ingestion] Page-based PDF chunking fallback: {exc}")

    # Default paragraph chunking
    paragraphs = [p.strip() for p in doc_text.split("\n\n") if p.strip()]
    buf = ""

    for para in paragraphs:
        if len(buf) + len(para) < 800:
            buf = f"{buf}\n\n{para}".strip()
        else:
            if buf:
                chunks.append(
                    {
                        "text":              buf,
                        "timestamp":         "N/A",
                        "timestamp_seconds": 0,
                        "page":              "N/A",
                        "branch":            branch_name,
                        "source_file":       filename,
                        "media_path":        "",
                        "type":              "document",
                    }
                )
            buf = para

    if buf:
        chunks.append(
            {
                "text":              buf,
                "timestamp":         "N/A",
                "timestamp_seconds": 0,
                "page":              "N/A",
                "branch":            branch_name,
                "source_file":       filename,
                "media_path":        "",
                "type":              "document",
            }
        )

    return chunks


# ── Markdown Parent-Child Processing ──────────────────────────────────────────

def parse_timestamp_seconds(heading_text: str) -> tuple[str, int, str]:
    match = re.search(r'\[(?:(\d{1,2}):)?(\d{2}):(\d{2})\]', heading_text)
    if match:
        hours   = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        total_seconds = hours * 3600 + minutes * 60 + seconds
        formatted_time = match.group(0).strip("[]")
        cleaned_heading_without_brackets = heading_text.replace(match.group(0), "").strip()
        return formatted_time, total_seconds, cleaned_heading_without_brackets
    return "N/A", 0, heading_text.strip()


def process_markdown_for_parent_child(
    md_content: str,
    source_file: str,
    branch_name: str,
    doc_type: str = "media_markdown",
) -> tuple[dict, list[dict]]:
    """
    Parse structured markdown (from generation or direct .md upload) into Parent sections
    and Child chunks. Returns (parent_dict, child_chunks_list).
    """
    parent_dict  = {}
    child_chunks = []

    sections = re.split(r'\n(?=#{1,2}\s+)', md_content)
    if not sections or (len(sections) == 1 and not sections[0].strip()):
        return parent_dict, child_chunks

    for section in sections:
        section = section.strip()
        if not section:
            continue

        lines      = section.split("\n")
        first_line = lines[0].strip()

        if first_line.startswith("#"):
            heading_text        = re.sub(r'^#+\s*', '', first_line)
            parent_section_text = section
        else:
            heading_text        = "General Overview"
            parent_section_text = section

        formatted_time, total_seconds, clean_title = parse_timestamp_seconds(heading_text)
        if not clean_title:
            clean_title = "General Overview"

        parent_id = f"parent_{uuid.uuid4().hex[:12]}"

        parent_dict[parent_id] = {
            "parent_id":         parent_id,
            "topic_title":       clean_title,
            "parent_topic_title": clean_title,
            "parent_text":       parent_section_text,
            "content":           parent_section_text,
            "source":            source_file,
            "source_file":       source_file,
            "type":              doc_type,
        }

        raw_children = re.split(r'\n(?=###\s+)|\n\n', parent_section_text)

        for idx, child_text in enumerate(raw_children):
            child_text = child_text.strip()
            if len(child_text) < 30:
                continue

            def chunk_string(s, length=800, overlap=100):
                if len(s) <= 1200:
                    return [s]
                res = []
                i = 0
                while i < len(s):
                    res.append(s[i:i + length])
                    if i + length >= len(s):
                        break
                    i += length - overlap
                return res

            sub_chunks = chunk_string(child_text)

            for sub_idx, sub_text in enumerate(sub_chunks):
                chunk_id = f"{parent_id}_child_{idx}_{sub_idx}"
                child_chunks.append({
                    "chunk_id":   chunk_id,
                    # Top-level fields consumed by pipeline.py
                    "parent_id":  parent_id,
                    "topic_title": clean_title,
                    "source":     source_file,
                    "chunk_text": sub_text,
                    "text":       sub_text,
                    # Nested metadata for retriever / legacy paths
                    "metadata": {
                        "parent_id":         parent_id,
                        "source_file":       source_file,
                        "source":            source_file,
                        "branch":            branch_name,
                        "type":              doc_type,
                        "section_heading":   clean_title,
                        "topic_title":       clean_title,
                        "timestamp":         formatted_time,
                        "timestamp_seconds": total_seconds,
                        "page":              "N/A",
                        "media_path":        source_file,
                    }
                })

    return parent_dict, child_chunks
