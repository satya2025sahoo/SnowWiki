"""
src/ingestion.py
================
Document parsing, Semantic Parent-Child chunking, and ChromaDB vector indexing.

Supports:
  - Media  : .mp3, .mp4, .mkv  →  Groq Whisper transcription
  - Docs   : .pdf, .docx, .txt →  text extraction + paragraph chunking

Chunking Strategy (v2 — Semantic Parent-Child):
  1. LLM-based topic segmentation → Parent Sections (500–2 500 chars each)
  2. Overlapping ~200-word windows per parent → Child Chunks
  3. ChromaDB stores Child Chunks (with parent_id metadata)
  4. JSON key-value store keeps full Parent Sections for RAG prompt assembly

All LLM calls (summarisation, segmentation) are handled internally via Groq.
"""

from __future__ import annotations

import json
import os
import re
import uuid

import chromadb
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from docx import Document

from src.config import (
    CHROMA_DB_DIR,
    UPLOADS_DIR,
    EMBEDDING_MODEL_NAME,
    COLLECTION_NAME,
    PARENT_STORE_DIR,
)
from src.transcriber import (
    transcribe_media_groq,
    generate_file_summary,
    load_branch_state,
    save_branch_state,
    update_master_branch_summary,
)


# ── Singleton embedding model ──────────────────────────────────────────────────

_EMBEDDER: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    """Lazy-load and cache the SentenceTransformer model."""
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _EMBEDDER


def get_chroma_collection():
    """Return (or create) the persistent ChromaDB collection."""
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ── Directory helpers ──────────────────────────────────────────────────────────

def get_branch_upload_dir(branch_name: str) -> str:
    branch_dir = os.path.join(UPLOADS_DIR, branch_name)
    os.makedirs(branch_dir, exist_ok=True)
    return branch_dir


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


# ── Timestamp Helpers ──────────────────────────────────────────────────────────

def parse_timestamp_str(timestamp_str: str) -> int:
    """Convert 'MM:SS' or 'HH:MM:SS' string into total seconds."""
    parts = timestamp_str.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        pass
    return 0


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
    parent_id   = parent_section["parent_id"]
    topic_title = parent_section["topic_title"]
    source      = parent_section["source"]

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


# ── Parent Store Persistence ───────────────────────────────────────────────────

def _branch_safe(branch_name: str) -> str:
    """Sanitise branch name for use as a filesystem key."""
    return re.sub(r"[^\w\-]", "_", branch_name)


def save_parent_store(branch_name: str, parent_sections: list[dict]) -> None:
    """
    Append new parent sections to the branch's JSON key-value store.
    Keys are parent_id strings; values are parent section dicts.
    """
    store_path = os.path.join(PARENT_STORE_DIR, f"{_branch_safe(branch_name)}.json")
    if os.path.exists(store_path):
        try:
            with open(store_path, "r", encoding="utf-8") as f:
                store: dict = json.load(f)
        except Exception:
            store = {}
    else:
        store = {}

    for ps in parent_sections:
        store[ps["parent_id"]] = ps

    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)


def load_parent_store(branch_name: str) -> dict[str, dict]:
    """Load the branch's parent store JSON. Returns empty dict if not found."""
    store_path = os.path.join(PARENT_STORE_DIR, f"{_branch_safe(branch_name)}.json")
    if not os.path.exists(store_path):
        return {}
    try:
        with open(store_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[ingestion] Failed to load parent store for '{branch_name}': {exc}")
        return {}


# ── Chunking ───────────────────────────────────────────────────────────────────

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


# ── Main Ingestion Entry Point ─────────────────────────────────────────────────

def process_and_ingest_files(
    branch_name: str,
    file_objects: list,
    status_callback=None,
) -> None:
    """
    Main ingestion pipeline:
    1. Sort media files chronologically by filename.
    2. Save files to ./data/uploads/<branch>/.
    3. Media  → Groq Whisper STT → chunk → ChromaDB.
    4. Docs   → text extraction → chunk → ChromaDB.
    5. Generate per-file summaries, update branch state JSON.
    6. Synthesise Master Branch Summary.

    Args:
        branch_name:     Active session / branch name.
        file_objects:    List of Streamlit UploadedFile objects.
        status_callback: Optional callable(str) for UI status messages.
    """
    media_ext = {".mp4", ".mkv", ".mp3"}
    doc_ext   = {".pdf", ".docx", ".txt"}

    media_files = []
    doc_files   = []

    for f in file_objects:
        ext = os.path.splitext(f.name)[1].lower()
        if ext in media_ext:
            media_files.append(f)
        elif ext in doc_ext:
            doc_files.append(f)

    # Sort media chronologically by filename so multi-session ordering is preserved
    media_files.sort(key=lambda x: x.name)
    all_files = media_files + doc_files

    upload_dir = get_branch_upload_dir(branch_name)
    embedder   = get_embedder()
    collection = get_chroma_collection()
    state      = load_branch_state(branch_name)
    total      = len(all_files)

    for idx, f_obj in enumerate(all_files, start=1):
        filename = f_obj.name
        ext      = os.path.splitext(filename)[1].lower()
        save_path = os.path.join(upload_dir, filename)

        if status_callback:
            status_callback(f"Processing ({idx}/{total}): {filename}…")

        # Persist the uploaded bytes locally if not already on disk
        file_already_uploaded = os.path.exists(save_path)
        if not file_already_uploaded:
            with open(save_path, "wb") as out_f:
                out_f.write(f_obj.getbuffer())
        else:
            print(f"[ingestion] File '{filename}' already in uploads — skipping disk write.")

        is_media  = ext in media_ext
        file_text = ""

        if is_media:
            if status_callback:
                status_callback(f"Checking transcript for: {filename}…")
            file_text, _ = transcribe_media_groq(save_path, branch_name, filename)
        else:
            if status_callback:
                status_callback(f"Extracting text: {filename}…")
            file_text = extract_document_text(save_path, ext)

        # ── Semantic Parent-Child segmentation ───────────────────────────────
        if status_callback:
            status_callback(f"Segmenting into topic sections: {filename}…")

        parent_sections = segment_into_parent_sections(
            text=file_text,
            filename=filename,
            source=save_path if is_media else filename,
        )

        if parent_sections:
            save_parent_store(branch_name, parent_sections)

        # Generate child chunks from all parent sections
        all_children: list[dict] = []
        for ps in parent_sections:
            all_children.extend(split_into_children(ps))

        # ── Per-file summary ─────────────────────────────────────────────────
        if status_callback:
            status_callback(f"Generating summary: {filename}…")
        file_summary = generate_file_summary(
            file_text,
            filename,
            "Media" if is_media else "Document",
        )

        # Build topic list from parent section titles
        topics_list = [ps["topic_title"] for ps in parent_sections]

        state["files"][filename] = {
            "summary": file_summary,
            "topics":  topics_list,
            "type":    "media" if is_media else "document",
            "path":    save_path,
        }
        save_branch_state(branch_name, state)

        # ── ChromaDB indexing (Child Chunks only) ─────────────────────────────
        if all_children:
            if status_callback:
                status_callback(f"Indexing {len(all_children)} child chunks: {filename}…")

            documents  = [c["chunk_text"] for c in all_children]
            embeddings = embedder.encode(documents).tolist()
            ids        = [
                f"{branch_name}__{filename}__{i}" for i in range(len(all_children))
            ]
            metadatas  = [
                {
                    "branch":            branch_name,
                    "source_file":       filename,
                    "parent_id":         c["parent_id"],
                    "topic_title":       c["topic_title"],
                    "source":            c["source"],
                    # Legacy-compat fields
                    "timestamp":         "N/A",
                    "timestamp_seconds": 0,
                    "page":              "N/A",
                    "media_path":        save_path if is_media else "",
                    "type":              "media" if is_media else "document",
                }
                for c in all_children
            ]

            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )

    # Synthesise Master Branch Summary across all files
    if status_callback:
        status_callback("Synthesising Master Branch Summary…")
    update_master_branch_summary(branch_name)

    if status_callback:
        status_callback(f"✅ Successfully processed all {total} file(s)!")
