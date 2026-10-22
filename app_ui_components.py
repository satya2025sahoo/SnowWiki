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


# ── Phase 5: Marker-Based Image Renderer ───────────────────────────────────────
#
# The LLM is only allowed to CITE images by short ID: [IMG_xxxx].
# Paths are NEVER read from LLM output — only from the manifest dict
# {image_id: abs_path} that was resolved from SQLite in Phase 4.
#
# Safety properties:
#   • No path is taken from the LLM answer — eliminates path-traversal risk.
#   • IDs not in the manifest are logged and silently dropped (no broken images).
#   • The manifest is capped to 3 images upstream in route_handlers.py.

_IMG_MARKER_RE = re.compile(r'\[IMG_([A-Za-z0-9_\-]{4,64})\]')
# Keeps backward-compat for old ![alt](path) tags stored in chat history
_MD_IMAGE_RE = re.compile(r'(!\[([^\]]*?)\]\(([^)]+?)\))')


def render_answer_with_images(
    answer_text: str,
    branch_name: str = "",
    image_manifest: dict[str, str] | None = None,
) -> None:
    """
    Render the LLM answer with safe inline images.

    Phase 5 mode  (image_manifest provided):
      • Splits answer on [IMG_xxxx] markers.
      • Looks up abs_path from manifest — never from answer text.
      • IDs not in manifest are dropped with a debug log line.

    Legacy fallback (no manifest):
      • Falls back to the old ![alt](path) scanning for chat history messages
        that were stored before Phase 4 was active.
    """
    import logging as _log
    logger = _log.getLogger(__name__)

    if image_manifest:
        # ── Phase 5 path: marker-based swap ──────────────────────────────────
        segments = _IMG_MARKER_RE.split(answer_text)
        # split() with one group: [text, id, text, id, text, ...]
        i = 0
        while i < len(segments):
            seg = segments[i]
            if seg.strip():
                st.markdown(seg)
            i += 1
            if i < len(segments):
                img_id = f"IMG_{segments[i]}"
                abs_path = image_manifest.get(img_id)
                if abs_path and os.path.isfile(abs_path):
                    st.image(abs_path, caption=img_id, use_container_width=True)
                else:
                    logger.warning(
                        "Phase 5: IMG ID '%s' not in manifest or file missing — dropped.", img_id
                    )
                i += 1
        return

    # ── Legacy path: old ![alt](path) scanning for stored history messages ─────
    parts = _MD_IMAGE_RE.split(answer_text)
    i = 0
    while i < len(parts):
        segment = parts[i]
        if _MD_IMAGE_RE.match(segment):
            i += 1
            continue
        if segment.strip():
            st.markdown(segment)
        if i + 3 < len(parts):
            _full = parts[i + 1]
            alt   = parts[i + 2]
            path  = parts[i + 3]
            abs_path = _resolve_image_path(path, branch_name)
            if abs_path and os.path.exists(abs_path):
                st.image(abs_path, caption=alt if alt else None, use_container_width=True)
            else:
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
