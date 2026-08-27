"""
src/ingestion/pipeline.py
=========================
Main ingestion entry point: orchestrates media/document ingestion into ChromaDB.

Pipeline stages (per file):
  1. Save upload to ./data/uploads/<branch>/
  2. Media (.mp3) → Groq Whisper STT → generate_rolling_markdown → structured text
  3. Docs (.pdf, .docx, .txt) → extract_document_text → raw text
  4. segment_into_parent_sections → Parent Sections (LLM-based)
  5. split_into_children          → Child Chunks (~200 words, 30-word overlap)
  6. Embed child chunks → ChromaDB upsert
  7. generate_file_summary → per-file summary saved to branch state JSON
  8. update_master_branch_summary → synthesised branch-level summary
"""

from __future__ import annotations

import logging
import os
import uuid

logger = logging.getLogger(__name__)

from src.ingestion.core import (
    get_branch_upload_dir,
    get_embedder,
    get_chroma_collection,
    save_parent_store,
)
from src.ingestion.chunking import (
    extract_document_text,
    segment_into_parent_sections,
    split_into_children,
)
from src.ingestion.docx_utils import convert_docx_to_markdown
from src.transcriber import (
    transcribe_media_groq,
    generate_file_summary,
    load_branch_state,
    save_branch_state,
    update_master_branch_summary,
)
from src.markdown_generator import generate_rolling_markdown


def process_and_ingest_files(
    branch_name: str,
    file_objects: list,
    status_callback=None,
) -> None:
    """
    Main ingestion pipeline:
    1. Sort media files chronologically by filename.
    2. Save files to ./data/uploads/<branch>/.
    3. Media  → Groq Whisper STT → rolling Markdown → ChromaDB.
    4. Docs   → text extraction → chunk → ChromaDB.
    5. Generate per-file summaries, update branch state JSON.
    6. Synthesise Master Branch Summary.

    Args:
        branch_name:     Active session / branch name.
        file_objects:    List of Streamlit UploadedFile objects.
        status_callback: Optional callable(str) for UI status messages.
    """
    media_ext = {".mp3", ".mp4"}   # Groq Whisper accepts both natively — no ffmpeg needed
    doc_ext   = {".pdf", ".docx", ".txt", ".md"}

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
        filename  = f_obj.name
        ext       = os.path.splitext(filename)[1].lower()
        save_path = os.path.join(upload_dir, filename)

        if status_callback:
            status_callback(f"Processing ({idx}/{total}): {filename}…")

        # ── Persist the uploaded bytes locally if not already on disk ─────────
        file_already_uploaded = os.path.exists(save_path)
        if not file_already_uploaded:
            with open(save_path, "wb") as out_f:
                out_f.write(f_obj.getbuffer())
        else:
            print(f"[ingestion] File '{filename}' already in uploads — skipping disk write.")

        is_media      = ext in media_ext
        file_text     = ""
        markdown_path = ""

        # ── Text extraction / transcription ───────────────────────────────────
        if is_media:
            if status_callback:
                status_callback(f"Checking transcript for: {filename}…")
            raw_transcript_text, _ = transcribe_media_groq(save_path, branch_name, filename)
            if status_callback:
                status_callback(f"Generating structured Markdown: {filename}…")
            file_text, markdown_path = generate_rolling_markdown(raw_transcript_text, filename, branch_name)
        elif ext == ".md":
            if status_callback:
                status_callback(f"Extracting markdown: {filename}…")
            with open(save_path, "r", encoding="utf-8", errors="ignore") as f:
                file_text = f.read()
            markdown_path = save_path
        elif ext == ".docx":
            if status_callback:
                status_callback(f"Converting DOCX to Markdown: {filename}…")
            file_text = convert_docx_to_markdown(save_path)
            branch_dir = get_branch_upload_dir(branch_name)
            out_name = f"{os.path.splitext(filename)[0]}.md"
            markdown_path = os.path.join(branch_dir, out_name)
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(file_text)
        else:
            if status_callback:
                status_callback(f"Extracting text: {filename}…")
            file_text = extract_document_text(save_path, ext)

        # ── Semantic Parent-Child segmentation ────────────────────────────────
        if status_callback:
            status_callback(f"Segmenting into topic sections: {filename}…")

        if ext in {".md", ".docx"} or is_media:
            from src.ingestion.chunking import process_markdown_for_parent_child
            doc_type = "media_markdown" if is_media else "document_markdown"
            parent_dict, all_children = process_markdown_for_parent_child(file_text, filename, branch_name, doc_type)
            parent_sections = list(parent_dict.values())
        else:
            parent_sections = segment_into_parent_sections(
                text=file_text,
                filename=filename,
                source=save_path if is_media else filename,
            )

        if parent_sections:
            save_parent_store(branch_name, parent_sections)

        # ── Generate child chunks from all parent sections (Docs only) ────────
        if not (ext in {".md", ".docx"} or is_media):
            all_children: list[dict] = []
            for ps in parent_sections:
                all_children.extend(split_into_children(ps))

        # ── Per-file summary ──────────────────────────────────────────────────
        if status_callback:
            status_callback(f"Generating summary: {filename}…")
        file_summary = generate_file_summary(
            file_text,
            filename,
            "Media" if (is_media or ext == ".md") else "Document",
        )

        # Build topic list from parent section titles
        topics_list = [ps["topic_title"] for ps in parent_sections]

        state["files"][filename] = {
            "summary": file_summary,
            "topics":  topics_list,
            "type":    "media" if is_media else "document",
            "path":    save_path,
        }
        if markdown_path:
            state["files"][filename]["markdown_path"] = markdown_path
        save_branch_state(branch_name, state)

        # ── ChromaDB indexing (Child Chunks only) ─────────────────────────────
        if all_children:
            if status_callback:
                status_callback(f"Indexing {len(all_children)} child chunks: {filename}…")

            documents  = [c.get("chunk_text") or c.get("text", "") for c in all_children]
            embeddings = embedder.encode(documents).tolist()
            ids        = [
                f"{branch_name}__{filename}__{i}" for i in range(len(all_children))
            ]

            def _safe_meta(c: dict) -> dict:
                """Extract metadata safely, checking both top-level and nested 'metadata' sub-dict."""
                meta       = c.get("metadata", {})
                parent_id  = c.get("parent_id") or meta.get("parent_id")
                topic_title = c.get("topic_title") or meta.get("topic_title", "")
                source     = c.get("source") or meta.get("source", filename)
                if not parent_id:
                    parent_id = f"parent_fallback_{uuid.uuid4().hex[:8]}"
                    logger.warning(
                        "Missing parent_id for chunk in '%s'. Assigned fallback ID: %s",
                        filename, parent_id,
                    )
                return {
                    "branch":            branch_name,
                    "source_file":       filename,
                    "parent_id":         parent_id,
                    "topic_title":       topic_title,
                    "source":            source,
                    # Legacy-compat fields
                    "timestamp":         meta.get("timestamp", "N/A"),
                    "timestamp_seconds": meta.get("timestamp_seconds", 0),
                    "page":              meta.get("page", "N/A"),
                    "media_path":        save_path if is_media else "",
                    "type":              "media" if is_media else "document",
                }

            metadatas = [_safe_meta(c) for c in all_children]

            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )

    # ── Synthesise Master Branch Summary across all files ─────────────────────
    if status_callback:
        status_callback("Synthesising Master Branch Summary…")
    update_master_branch_summary(branch_name)

    if status_callback:
        status_callback(f"✅ Successfully processed all {total} file(s)!")
