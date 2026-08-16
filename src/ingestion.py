"""
src/ingestion.py
================
Document parsing, file chunking, and ChromaDB vector indexing.

Supports:
  - Media  : .mp3, .mp4, .mkv  →  Groq Whisper transcription
  - Docs   : .pdf, .docx, .txt →  text extraction + paragraph chunking

All LLM calls (summarisation) are handled internally via Groq;
no external client object is required by callers.
"""

from __future__ import annotations

import os
import re

import chromadb
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from docx import Document

from src.config import (
    CHROMA_DB_DIR,
    UPLOADS_DIR,
    EMBEDDING_MODEL_NAME,
    COLLECTION_NAME,
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

        # Persist the uploaded bytes locally
        with open(save_path, "wb") as out_f:
            out_f.write(f_obj.getbuffer())

        is_media  = ext in media_ext
        file_text = ""
        chunks: list[dict] = []

        if is_media:
            if status_callback:
                status_callback(f"Transcribing via Groq Whisper: {filename}…")
            file_text, _ = transcribe_media_groq(save_path, branch_name, filename)
            chunks = parse_transcript_chunks(file_text, filename, branch_name, save_path)
        else:
            if status_callback:
                status_callback(f"Extracting text: {filename}…")
            file_text = extract_document_text(save_path, ext)
            chunks    = chunk_document_text(file_text, filename, branch_name, save_path, ext)

        # Per-file summary
        if status_callback:
            status_callback(f"Generating summary: {filename}…")
        file_summary = generate_file_summary(
            file_text,
            filename,
            "Media" if is_media else "Document",
        )

        state["files"][filename] = {
            "summary": file_summary,
            "type":    "media" if is_media else "document",
            "path":    save_path,
        }
        save_branch_state(branch_name, state)

        # Vector index in ChromaDB
        if chunks:
            if status_callback:
                status_callback(f"Indexing {len(chunks)} chunks: {filename}…")

            documents  = [c["text"] for c in chunks]
            embeddings = embedder.encode(documents).tolist()
            ids        = [f"{branch_name}__{filename}__{i}" for i in range(len(chunks))]
            metadatas  = [
                {
                    "branch":            c["branch"],
                    "source_file":       c["source_file"],
                    "timestamp":         c.get("timestamp", "N/A"),
                    "timestamp_seconds": c.get("timestamp_seconds", 0),
                    "page":              c.get("page", "N/A"),
                    "media_path":        c.get("media_path", ""),
                    "type":              c.get("type", "document"),
                }
                for c in chunks
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
