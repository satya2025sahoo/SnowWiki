"""
src/ingestion/__init__.py
=========================
Public API of the ingestion package.

Re-exports the symbols that external modules (app.py, src/retriever.py, etc.)
previously imported directly from the flat src/ingestion.py file, so no other
file needs to change its import paths.

Module layout
─────────────
  core.py       — ChromaDB client, embedder, upload dir, parent store, timestamp
  chunking.py   — text extraction, LLM segmentation, child chunking, transcript parsing
  docx_utils.py — DOCX → Markdown conversion utilities
  pipeline.py   — process_and_ingest_files (main entry point)
"""

from src.ingestion.core import (
    get_embedder,
    get_chroma_collection,
    get_branch_upload_dir,
    parse_timestamp_str,
    save_parent_store,
    load_parent_store,
)
from src.ingestion.chunking import (
    extract_document_text,
    segment_into_parent_sections,
    split_into_children,
    parse_transcript_chunks,
    chunk_document_text,
    process_markdown_for_parent_child,
)
from src.ingestion.docx_utils import convert_docx_to_markdown
from src.ingestion.pipeline import process_and_ingest_files

__all__ = [
    # core
    "get_embedder",
    "get_chroma_collection",
    "get_branch_upload_dir",
    "parse_timestamp_str",
    "save_parent_store",
    "load_parent_store",
    # chunking
    "extract_document_text",
    "segment_into_parent_sections",
    "split_into_children",
    "parse_transcript_chunks",
    "chunk_document_text",
    "process_markdown_for_parent_child",
    # docx_utils
    "convert_docx_to_markdown",
    # pipeline
    "process_and_ingest_files",
]
