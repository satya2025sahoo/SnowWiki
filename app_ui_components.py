"""
app_ui_components.py
====================
Reusable Streamlit UI components for the SnowWiki chat interface.

Extracted from app.py to keep rendering logic separate from app wiring.

Public API
----------
render_pipeline_trace(trace)
render_source_chunks(retrieved_chunks)
render_media_reference(msg_or_result, key_prefix)
render_web_sources(grounding_sources)
"""

from __future__ import annotations

import os
import re

import streamlit as st

from src.config import UPLOADS_DIR


# ── Inline Image Rendering from LLM Answer ─────────────────────────────────

# Regex to find Markdown image tags: ![alt text](image/path)
_MD_IMAGE_RE = re.compile(r'(!\[([^\]]*?)\]\(([^)]+?)\))')


def _resolve_image_path(rel_or_abs: str, branch_name: str = "") -> str | None:
    """
    Try to resolve a relative image path (e.g. 'images/img_1.png') to an
    absolute path on disk by searching the uploads directory.

    Search order:
      1. Already absolute and exists.
      2. Under UPLOADS_DIR/<branch_name>/<any_doc_folder>/images/<filename>
      3. Under UPLOADS_DIR/<branch_name>/images/<filename>  (legacy)
      4. Under UPLOADS_DIR recursively (slow fallback).
    """
    # Already absolute
    if os.path.isabs(rel_or_abs) and os.path.exists(rel_or_abs):
        return rel_or_abs

    filename = os.path.basename(rel_or_abs)

    # 1. Check branch-scoped per-file directories
    if branch_name:
        branch_dir = os.path.join(UPLOADS_DIR, branch_name)
        if os.path.isdir(branch_dir):
            for entry in os.scandir(branch_dir):
                candidate = os.path.join(entry.path, "images", filename)
                if os.path.exists(candidate):
                    return candidate
            # Legacy branch-level images/
            legacy = os.path.join(branch_dir, "images", filename)
            if os.path.exists(legacy):
                return legacy

    # 2. Broad recursive fallback across all branches
    for root, _dirs, files in os.walk(UPLOADS_DIR):
        if filename in files:
            return os.path.join(root, filename)

    return None


def render_answer_with_images(answer_text: str, branch_name: str = "") -> None:
    """
    Render the LLM answer in textbook layout:
      - Text segments are rendered with st.markdown()
      - Image tags `![alt](path)` are rendered inline with st.image()

    This is required because Streamlit cannot serve local filesystem images
    via st.markdown() — the browser cannot resolve 'images/img.png' paths.
    """
    parts = _MD_IMAGE_RE.split(answer_text)
    # split() with a group returns: [text, full_match, alt, path, text, full_match, ...]
    # Groups are: (full_match, alt_text, img_path)

    i = 0
    while i < len(parts):
        segment = parts[i]

        # Check if this segment is a full image tag match (every 4th element after split)
        # Pattern: text | full_match | alt | path | text | full_match | ...
        if _MD_IMAGE_RE.match(segment):
            # This is the full image markdown tag — skip; handled by next group
            i += 1
            continue

        # Render text segment
        if segment.strip():
            st.markdown(segment)

        # Check if next 3 elements form an image group (full_match, alt, path)
        if i + 3 < len(parts):
            _full = parts[i + 1]   # e.g. ![alt](path)
            alt   = parts[i + 2]   # e.g. "Flowchart of Discovery phases"
            path  = parts[i + 3]   # e.g. "images/img_1.png"

            abs_path = _resolve_image_path(path, branch_name)
            if abs_path and os.path.exists(abs_path):
                st.image(abs_path, caption=alt if alt else None, width="stretch")
            else:
                # Image not found on disk — show the markdown tag as fallback
                st.markdown(_full)

            i += 4
        else:
            i += 1


# ── Vision Debug Viewer ──────────────────────────────────────────────────

import json as _json


def render_vision_debug_viewer(branch_name: str) -> None:
    """
    Sidebar expander showing Qwen-VL extraction debug info for the active branch.
    Shows each image, its classification, and Qwen's raw extracted description.
    """
    branch_dir = os.path.join(UPLOADS_DIR, branch_name)
    if not os.path.isdir(branch_dir):
        return

    # Find all vision_debug.json files in branch
    debug_files = []
    for root, _dirs, files in os.walk(branch_dir):
        if "vision_debug.json" in files:
            debug_files.append(os.path.join(root, "vision_debug.json"))

    if not debug_files:
        return

    with st.expander("🔬 Vision Debug: Qwen-VL Extractions", expanded=False):
        for debug_path in debug_files:
            try:
                with open(debug_path, "r", encoding="utf-8") as f:
                    data = _json.load(f)
            except Exception:
                continue

            st.markdown(f"**📄 Document:** `{data.get('document', '?')}` — "
                        f"Model: `{data.get('vlm_model', '?')}` — "
                        f"Total Images: `{data.get('total_images', 0)}`")

            for entry in data.get("extractions", []):
                img_path = entry.get("full_path", "")
                col1, col2 = st.columns([1, 2])
                with col1:
                    if os.path.exists(img_path):
                        st.image(img_path, caption=entry.get("filename", ""), width="stretch")
                    else:
                        st.caption(f"🖼️ {entry.get('filename', 'unknown')}")
                with col2:
                    st.markdown(f"**Type:** `{entry.get('image_classification', 'Unknown')}`")
                    st.markdown(f"**Extracted @ {entry.get('timestamp', '')}**")
                    st.code(entry.get("raw_vlm_output", ""), language="text")
                st.divider()


# ── Pipeline Trace Visualiser ─────────────────────────────────────────────────

def render_pipeline_trace(trace: dict | None) -> None:
    """Render a detailed multi-stage trace of the query routing process."""
    if not trace or not isinstance(trace, dict):
        return

    with st.expander("🛠️ View Pipeline Trace", expanded=False):
        st.subheader("🧠 Multi-Stage Routing & RAG Pipeline Trace")

        # Stage 1: Intent Classifier
        s1 = trace.get("stage1_classifier")
        if s1 and isinstance(s1, dict):
            st.markdown("#### **Stage 1 — Intent & Routing Classifier**")
            st.markdown(f"- **Classifier Model:** `{s1.get('model')}`")
            st.markdown(
                f"- **Parsed Intent:** `{s1.get('intent')}` &nbsp;|&nbsp; "
                f"**Sub-Intent:** `{s1.get('rag_sub_intent')}` &nbsp;|&nbsp; "
                f"**Confidence:** `{s1.get('confidence')}`"
            )
            with st.expander("View Classifier Prompt & Raw Output", expanded=False):
                st.markdown("**System Prompt:**")
                st.code(s1.get("system_prompt", ""), language="text")
                st.markdown("**User Message:**")
                st.code(s1.get("user_input", ""), language="text")
                st.markdown("**Raw LLM Output:**")
                st.code(s1.get("raw_output", ""), language="json")

        # Stage 2: Context Retrieval & Generation
        s2_ret = trace.get("stage2_retrieval")
        s2_gen = trace.get("stage2_generation")

        if (s2_ret and isinstance(s2_ret, dict)) or (s2_gen and isinstance(s2_gen, dict)):
            st.markdown("#### **Stage 2 — Context Retrieval & Core Generation**")
            if s2_ret:
                st.markdown(f"- **Retrieval Mode:** `{s2_ret.get('method')}`")
                if "similarity_score" in s2_ret:
                    st.markdown(f"- **Max Match Similarity:** `{s2_ret.get('similarity_score')}`")
                if "child_chunks_found" in s2_ret:
                    st.markdown(
                        f"- **Matching Child Chunks:** `{s2_ret.get('child_chunks_found')}` &nbsp;|&nbsp; "
                        f"**Unique Parent Topics:** `{len(s2_ret.get('parent_ids_fetched', []))}`"
                    )
                if "num_results" in s2_ret:
                    st.markdown(f"- **Web Matches Fetched:** `{s2_ret.get('num_results')}`")
                    if s2_ret.get("urls"):
                        st.markdown("**Consulted URLs:**")
                        for url in s2_ret["urls"]:
                            st.markdown(f"  - [{url}]({url})")

            if s2_gen:
                st.markdown(f"- **Response Generation Model:** `{s2_gen.get('model')}`")
                with st.expander("View Context & Draft Generation", expanded=False):
                    st.markdown("**Context Block Sent:**")
                    st.code(s2_gen.get("context_sent", ""), language="text")
                    st.markdown("**Draft Output (Raw RAG Response):**")
                    st.code(s2_gen.get("draft_output", ""), language="text")


# ── Source Chunk Inspector ─────────────────────────────────────────────────────

def render_source_chunks(retrieved_chunks: list[dict]) -> None:
    """Render the 'View Referenced Source Chunks' expander block."""
    if not retrieved_chunks:
        return

    with st.expander("📄 View Referenced Source Chunks", expanded=False):
        for idx, chunk in enumerate(retrieved_chunks, 1):
            page_time    = chunk.get("page_or_timestamp") or chunk.get("page") or chunk.get("timestamp") or "N/A"
            score_val    = chunk.get("score") if chunk.get("score") is not None else chunk.get("similarity_score", "N/A")
            parent_title = chunk.get("parent_topic_title") or chunk.get("topic_title") or ""
            parent_text  = chunk.get("parent_text", "")

            if parent_title:
                st.markdown(
                    f"**📄 Parent Topic:** `{parent_title}` &nbsp;|&nbsp; "
                    f"📁 **Source:** `{chunk.get('source', 'Unknown')}` &nbsp;|&nbsp; "
                    f"🎯 **Similarity:** `{score_val}`"
                )
                st.caption(f"↳ Matched Child Chunk @ {page_time}")
                st.info(chunk.get("chunk_text", ""))
                has_image = chunk.get("has_image", False)
                if has_image and chunk.get("image_paths"):
                    st.caption("🖼️ Attached Image(s)")
                    for img_path in chunk["image_paths"].split(","):
                        if os.path.exists(img_path):
                            st.image(img_path)
                if parent_text:
                    with st.expander("🔎 View Full Parent Section sent to LLM", expanded=False):
                        st.markdown(parent_text)
            else:
                # Legacy chunk display
                st.markdown(
                    f"**Chunk #{idx}** | 📁 **Source:** `{chunk.get('source', 'Unknown')}` | "
                    f"📖 **Page/Time:** `{page_time}` | "
                    f"🎯 **Similarity:** `{score_val}`"
                )
                st.info(chunk.get("chunk_text", ""))
                has_image = chunk.get("has_image", False)
                if has_image and chunk.get("image_paths"):
                    st.caption("🖼️ Attached Image(s)")
                    for img_path in chunk["image_paths"].split(","):
                        if os.path.exists(img_path):
                            st.image(img_path)
            st.divider()


# ── Media Reference Player ────────────────────────────────────────────────────

def render_media_reference(data: dict) -> None:
    """
    Render the video/audio timestamp reference block for internal RAG hits.

    Accepts either a persisted message dict or a live result dict — both share
    the same key names (source_type, media_path, source_file, timestamp,
    timestamp_seconds, top_chunk).
    """
    if (
        data.get("source_type") != "internal"
        or not data.get("media_path")
        or not os.path.exists(data["media_path"])
    ):
        return

    st.markdown("---")
    st.markdown(
        f"**🎥 Source:** `{data.get('source_file')}` @ `{data.get('timestamp')}`"
    )
    ext       = os.path.splitext(data["media_path"])[1].lower()
    start_sec = data.get("timestamp_seconds", 0)
    if ext in {".mp4", ".mkv"}:
        st.video(data["media_path"], start_time=start_sec)
    elif ext == ".mp3":
        st.audio(data["media_path"], start_time=start_sec)

    with st.expander("🔍 Raw Transcript Chunk"):
        st.code(data.get("top_chunk", ""))


# ── Web Grounding Sources ─────────────────────────────────────────────────────

def render_web_sources(grounding_sources: list[dict]) -> None:
    """Render web source links for Google Search fallback responses."""
    if not grounding_sources:
        return

    st.markdown("---")
    st.markdown("**🌐 Sources:**")
    for src in grounding_sources:
        st.markdown(f"- [{src.get('title', 'ServiceNow Docs')}]({src.get('url', '#')})")
