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
    get_file_dir,
    get_file_image_dir,
    get_embedder,
    get_chroma_collection,
    save_parent_store,
)
from src.ingestion.chunking import (
    extract_document_text,
    segment_into_parent_sections,
    split_into_children,
    build_image_chunks,
    deduplicate_chunks,
)

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

    # Pre-pass: collect all existing images for rule 4 (phash doc repeats)
    image_paths_by_doc = {}
    if os.path.exists(upload_dir):
        for doc_folder in os.listdir(upload_dir):
            doc_img_dir = os.path.join(upload_dir, doc_folder, "images")
            if os.path.isdir(doc_img_dir):
                paths = [os.path.join(doc_img_dir, f) for f in os.listdir(doc_img_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
                if paths:
                    image_paths_by_doc[doc_folder] = paths
    
    from src.ingestion.image_classifier import build_phash_doc_counts, classify_image, upsert_asset
    doc_phash_counts = build_phash_doc_counts(image_paths_by_doc)

    for idx, f_obj in enumerate(all_files, start=1):
        filename  = f_obj.name
        ext       = os.path.splitext(filename)[1].lower()

        # ── Per-file folder: data/uploads/<branch>/<file_stem>/ ───────────────
        file_dir  = get_file_dir(branch_name, filename)
        image_dir = get_file_image_dir(branch_name, filename)
        save_path = os.path.join(file_dir, filename)

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

            from src.ingestion.core import fix_markdown_image_paths
            fixed_text = fix_markdown_image_paths(file_text)
            if fixed_text != file_text:
                file_text = fixed_text
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(file_text)

            # ── Sliding-window LLM rewrite (clean Markdown + rolling summary) ──
            if status_callback:
                status_callback(f"Rewriting Markdown with sliding-window LLM: {filename}…")
            from src.ingestion.rolling_doc_markdown import process_markdown_rolling_markdown
            stem = os.path.splitext(filename)[0]
            clean_md_path = os.path.join(file_dir, f"{stem}_clean.md")
            process_markdown_rolling_markdown(save_path, clean_md_path)
            # Use the cleaned output for downstream indexing
            with open(clean_md_path, "r", encoding="utf-8", errors="ignore") as f:
                file_text = f.read()
            markdown_path = clean_md_path

        elif ext == ".docx":
            if status_callback:
                status_callback(f"Converting DOCX to Markdown (with images): {filename}…")
            from src.ingestion.docx_utils.converter import convert_docx_to_markdown

            image_dir = os.path.join(file_dir, "images")
            file_text = convert_docx_to_markdown(save_path, branch_name=branch_name, image_dir=image_dir)

            # Stage 1: Classify and Cache all extracted images
            if status_callback:
                status_callback(f"Running junk filter & OCR on images: {filename}…")
            if os.path.exists(image_dir):
                for img_file in os.listdir(image_dir):
                    if not img_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        continue
                    img_path = os.path.join(image_dir, img_file)
                    verdict = classify_image(img_path, doc_phash_counts)
                    asset_record = {
                        "sha256": verdict.sha256,
                        "context_hash": "", 
                        "model_version": "",
                        "prompt_version": "v2.0",
                        "junk": verdict.junk,
                        "reason": verdict.reason,
                        "route": verdict.route,
                        "ocr_text": verdict.ocr_text,
                        "description": "",
                        "doc_id": filename,
                        "branch": branch_name,
                        "image_id": verdict.image_id,
                        "rel_path": f"images/{img_file}",
                        "abs_path": img_path,
                        "page": 1, 
                        "parent_id": ""
                    }
                    upsert_asset(asset_record)

            out_name = f"{os.path.splitext(filename)[0]}.md"
            markdown_path = os.path.join(file_dir, out_name)
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(file_text)

            from src.ingestion.enricher import enrich_markdown_with_images
            if status_callback:
                status_callback(f"Enriching images with VLM descriptions: {filename}…")
            enrich_markdown_with_images(markdown_path, branch_name, image_dir, status_callback)

            # ── Sliding-window LLM rewrite: * bullets + parent-child + rolling summary ──
            if status_callback:
                status_callback(f"Rewriting Markdown with sliding-window LLM: {filename}…")
            from src.ingestion.rolling_doc_markdown import process_markdown_rolling_markdown
            process_markdown_rolling_markdown(markdown_path, markdown_path)
            with open(markdown_path, "r", encoding="utf-8", errors="ignore") as f:
                file_text = f.read()

        elif ext == ".pdf":
            if status_callback:
                status_callback(f"Converting PDF to Markdown (with images): {filename}…")
            from src.ingestion.pdf_utils.converter import convert_pdf_to_markdown

            image_dir = os.path.join(file_dir, "images")
            file_text = convert_pdf_to_markdown(save_path, branch_name=branch_name, image_dir=image_dir)

            # Stage 1: Classify and Cache all extracted images
            if status_callback:
                status_callback(f"Running junk filter & OCR on images: {filename}…")
            if os.path.exists(image_dir):
                for img_file in os.listdir(image_dir):
                    if not img_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        continue
                    img_path = os.path.join(image_dir, img_file)
                    verdict = classify_image(img_path, doc_phash_counts)
                    asset_record = {
                        "sha256": verdict.sha256,
                        "context_hash": "", 
                        "model_version": "",
                        "prompt_version": "v2.0",
                        "junk": verdict.junk,
                        "reason": verdict.reason,
                        "route": verdict.route,
                        "ocr_text": verdict.ocr_text,
                        "description": "",
                        "doc_id": filename,
                        "branch": branch_name,
                        "image_id": verdict.image_id,
                        "rel_path": f"images/{img_file}",
                        "abs_path": img_path,
                        "page": 1, 
                        "parent_id": ""
                    }
                    upsert_asset(asset_record)

            out_name = f"{os.path.splitext(filename)[0]}.md"
            markdown_path = os.path.join(file_dir, out_name)
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(file_text)

            from src.ingestion.enricher import enrich_markdown_with_images
            if status_callback:
                status_callback(f"Enriching images with VLM descriptions: {filename}…")
            enrich_markdown_with_images(markdown_path, branch_name, image_dir, status_callback)

            # ── Sliding-window LLM rewrite: * bullets + parent-child + rolling summary ──
            if status_callback:
                status_callback(f"Rewriting Markdown with sliding-window LLM: {filename}…")
            from src.ingestion.rolling_doc_markdown import process_markdown_rolling_markdown
            process_markdown_rolling_markdown(markdown_path, markdown_path)
            with open(markdown_path, "r", encoding="utf-8", errors="ignore") as f:
                file_text = f.read()
        else:
            if status_callback:
                status_callback(f"Extracting text: {filename}…")
            file_text = extract_document_text(save_path, ext)

        # ── Semantic Parent-Child segmentation ────────────────────────────────
        if status_callback:
            status_callback(f"Segmenting into topic sections: {filename}…")

        if ext in {".md", ".docx", ".pdf"} or is_media:
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
        if not (ext in {".md", ".docx", ".pdf"} or is_media):
            all_children: list[dict] = []
            for ps in parent_sections:
                all_children.extend(split_into_children(ps))

        # ── Phase 3: Append standalone image_chunks (DOCX / PDF only) ────────
        if ext in {".docx", ".pdf"} and os.path.exists(image_dir):
            if status_callback:
                status_callback(f"Building image embeddings: {filename}…")
            doc_type = "document_markdown"
            first_parent_id = parent_sections[0]["parent_id"] if parent_sections else ""
            img_chunks = build_image_chunks(
                branch_name=branch_name,
                source_file=filename,
                image_dir=image_dir,
                parent_id=first_parent_id,
                doc_type=doc_type,
            )
            all_children.extend(img_chunks)
            logger.info(
                "Phase 3: added %d image_chunk(s) for %s",
                len(img_chunks), filename,
            )

        # ── Phase 3: Deduplicate before embedding ─────────────────────────────
        all_children = deduplicate_chunks(all_children)
        logger.info("Phase 3: %d unique chunks after dedup for %s", len(all_children), filename)

        # ── Per-file summary ──────────────────────────────────────────────────
        if status_callback:
            status_callback(f"Generating summary: {filename}…")
        file_summary = generate_file_summary(
            file_text,
            filename,
            "Media" if (is_media or ext == ".md") else "Document",
        )
        
        summary_path = os.path.join(file_dir, "_summary.md")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(f"# Summary for {filename}\n\n{file_summary}")

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
                meta        = c.get("metadata", {})
                parent_id   = c.get("parent_id") or meta.get("parent_id")
                topic_title = c.get("topic_title") or meta.get("topic_title", "")
                source      = c.get("source") or meta.get("source", filename)
                chunk_type  = c.get("chunk_type") or meta.get("chunk_type", "text")
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
                    "chunk_type":        chunk_type,
                    "image_id":          meta.get("image_id", ""),
                    "image_ids":         meta.get("image_ids", ""),
                    "abs_path":          meta.get("abs_path", ""),
                    "rel_path":          meta.get("rel_path", ""),
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

    # Invalidate cached BM25 index so new chunks are included in hybrid search
    try:
        from src.hybrid_search import invalidate_branch_index
        invalidate_branch_index(branch_name)
    except Exception:
        pass

    if status_callback:
        status_callback(f"✅ Successfully processed all {total} file(s)!")
