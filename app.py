"""
app.py
======
SnowWiki Smart Routing AI Agent — Streamlit Frontend

ChatGPT-style interface with:
  - 4-stage smart routing badges
  - Branch / session management with persistent history
  - + New Chat that clears the active thread without losing branch history
  - File upload and processing sidebar
  - No API key inputs — all secrets loaded from .env

Design & UI helpers live in:
  app_styles.py        — inject_css()
  app_ui_components.py — render_pipeline_trace(), render_source_chunks(),
                         render_media_reference(), render_web_sources(),
                         render_answer_with_images(), render_vision_debug_viewer()
"""

import json
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# ── Load .env secrets before anything else ────────────────────────────────────
load_dotenv()

# ── Backend imports ────────────────────────────────────────────────────────────
from src.config import PROJECT_STATES_DIR, GROQ_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID, USE_LOCAL_LLM
from src.transcriber import load_branch_state
from src.ingestion import (
    process_and_ingest_files,
    enqueue_ingestion_job,
    get_job_status,
    get_active_jobs,
    get_recent_jobs,
)
from src.retriever import query_snow_wiki
from src.memory import MemoryManager
from src.tracing import init_tracing

# ── UI helpers ─────────────────────────────────────────────────────────────────
from app_styles import inject_css
from app_ui_components import (
    render_pipeline_trace,
    render_source_chunks,
    render_media_reference,
    render_web_sources,
    render_answer_with_images,
    render_vision_debug_viewer,
)

# ── Initialize LangSmith tracing (no-op if LANGSMITH_API_KEY is absent) ───────
init_tracing()

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SnowWiki | Smart Routing AI",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject CSS design system ───────────────────────────────────────────────────
inject_css()

# ── Singleton Memory Manager ───────────────────────────────────────────────────
memory_manager = MemoryManager()


# ── Session State Bootstrap ───────────────────────────────────────────────────

def _discover_branches() -> list[str]:
    """Return branch names discovered from project states directory."""
    branches: list[str] = []
    if os.path.exists(PROJECT_STATES_DIR):
        for f in os.listdir(PROJECT_STATES_DIR):
            if f.endswith(".json"):
                branches.append(f[:-5])
    return branches or ["CSM Training", "ITOM Deep Dive", "Weekly Tuesday KT"]


if "branches" not in st.session_state:
    st.session_state.branches = _discover_branches()

if "active_branch" not in st.session_state:
    st.session_state.active_branch = st.session_state.branches[0]

if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = memory_manager.create_session(st.session_state.active_branch)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "show_branch_input" not in st.session_state:
    st.session_state.show_branch_input = False

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0


# ── Helper: API Status Indicators ─────────────────────────────────────────────

def _status_html(label: str, ok: bool) -> str:
    cls  = "status-online" if ok else "status-offline"
    icon = "✓" if ok else "✗"
    return (
        f'<span class="status-label">'
        f'<span class="status-dot {cls}"></span> {icon} {label}'
        f"</span>"
    )

def _relative_time(dt_str: str) -> str:
    try:
        dt   = datetime.fromisoformat(dt_str)
        diff = datetime.now() - dt
        if diff.days > 0:
            return f"{diff.days}d ago"
        hrs = diff.seconds // 3600
        if hrs > 0:
            return f"{hrs}h ago"
        mins = diff.seconds // 60
        if mins > 0:
            return f"{mins}m ago"
        return "Just now"
    except Exception:
        return ""


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ❄️ SnowWiki Engine")

    # ── API Status (read from env; no user input) ──────────────────────
    # groq_ok is True if Groq key exists OR if local LLM mode is enabled.
    groq_ok   = bool(GROQ_API_KEY) or USE_LOCAL_LLM
    google_ok = bool(GOOGLE_API_KEY and GOOGLE_CSE_ID)

    st.markdown(
        '<div class="status-row">'
        + _status_html("Groq API" if not USE_LOCAL_LLM else "Local LLM", groq_ok)
        + "&nbsp;&nbsp;"
        + _status_html("Google Search", google_ok)
        + "</div>",
        unsafe_allow_html=True,
    )

    if not groq_ok:
        st.error("⚠️ No LLM backend configured. Set GROQ_API_KEY or USE_LOCAL_LLM=true in .env.")
    if not google_ok:
        st.caption("ℹ️ Google CSE keys missing — web fallback disabled.")

    st.divider()

    # ── + New Chat ─────────────────────────────────────────────────────────
    st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
    if st.button("＋ New Chat", use_container_width=True, key="new_chat_btn"):
        st.session_state.active_session_id = memory_manager.create_session(st.session_state.active_branch)
        st.session_state.messages = []
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Chat History ───────────────────────────────────────────────────────
    st.markdown("### 💬 Chat History")
    sessions = memory_manager.list_sessions(st.session_state.active_branch)
    sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    if not sessions:
        st.caption("No history yet.")
    else:
        # Show top 10 sessions to keep sidebar clean
        for s in sessions[:10]:
            s_id     = s.get("id")
            title    = s.get("title", "New Chat")
            time_str = _relative_time(s.get("created_at", ""))

            btn_label = f"{title[:25]}... ({time_str})" if len(title) > 25 else f"{title} ({time_str})"

            if s_id == st.session_state.active_session_id:
                st.markdown('<div class="session-btn-active">', unsafe_allow_html=True)
                st.button(btn_label, key=f"sess_{s_id}", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                if st.button(btn_label, key=f"sess_{s_id}", use_container_width=True):
                    st.session_state.active_session_id = s_id
                    st.session_state.messages = memory_manager.load_session(
                        st.session_state.active_branch, s_id
                    ).get("messages", [])
                    st.rerun()

    st.divider()

    # ── Branch / Session Manager ───────────────────────────────────────────
    st.markdown("### 📁 Training Branches")

    col_add_btn, _ = st.columns([1, 0.01])
    with col_add_btn:
        if st.button("➕ New Branch", key="add_branch_btn", use_container_width=True):
            st.session_state.show_branch_input = True

    if st.session_state.show_branch_input:
        new_branch_name = st.text_input(
            "Branch name:", placeholder="e.g. SPM Masterclass", key="new_branch_input"
        )
        col_create, col_cancel = st.columns(2)
        with col_create:
            if st.button("Create", key="create_branch"):
                if new_branch_name and new_branch_name.strip():
                    clean = new_branch_name.strip()
                    if clean not in st.session_state.branches:
                        st.session_state.branches.append(clean)
                    st.session_state.active_branch     = clean
                    st.session_state.active_session_id = memory_manager.create_session(clean)
                    st.session_state.messages          = []
                    st.session_state.show_branch_input = False
                    st.rerun()
        with col_cancel:
            if st.button("Cancel", key="cancel_branch"):
                st.session_state.show_branch_input = False
                st.rerun()

    selected_branch = st.selectbox(
        "Active Branch:",
        options=st.session_state.branches,
        index=(
            st.session_state.branches.index(st.session_state.active_branch)
            if st.session_state.active_branch in st.session_state.branches
            else 0
        ),
        key="branch_selector",
    )
    if selected_branch != st.session_state.active_branch:
        st.session_state.active_branch     = selected_branch
        st.session_state.active_session_id = memory_manager.create_session(selected_branch)
        st.session_state.messages          = []
        st.rerun()

    st.divider()

    # ── File Uploader ──────────────────────────────────────────────────────
    st.markdown(f"### 📤 Upload to `{st.session_state.active_branch}`")
    uploaded_files = st.file_uploader(
        "Select training media or docs:",
        type=["mp4", "mkv", "mp3", "pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Supported: .mp4 .mkv .mp3 .pdf .docx .txt",
        key=f"file_uploader_{st.session_state.uploader_key}",
    )

    @st.fragment(run_every="2s")
    def render_active_ingestion_jobs(branch_name: str) -> None:
        """Reactive background task monitor that auto-refreshes every 2s without full-page reloads."""
        recent_jobs = get_recent_jobs(branch_name=branch_name, limit=3)
        if not recent_jobs:
            return

        with st.container():
            st.markdown("#### ⚙️ Background Tasks")
            for j in recent_jobs:
                status = j["status"]
                progress = j.get("progress_pct", 0)
                stage = j.get("stage_message", "")

                try:
                    files = json.loads(j.get("files_json", "[]"))
                    fnames = ", ".join(f["name"] for f in files[:2])
                    if len(files) > 2:
                        fnames += f" (+{len(files)-2} more)"
                except Exception:
                    fnames = "Document"

                if status == "RUNNING":
                    st.caption(f"**Processing:** `{fnames}`")
                    st.progress(min(max(progress, 5), 100) / 100.0)
                    st.info(f"⏳ {stage}")
                elif status == "QUEUED":
                    st.caption(f"**Queued:** `{fnames}`")
                    st.warning("🕒 Awaiting worker slot…")
                elif status == "COMPLETED":
                    st.success(f"✅ `{fnames}` indexed successfully!")
                elif status == "FAILED":
                    st.error(f"❌ `{fnames}` failed: {stage}")

    if uploaded_files:
        if st.button(
            "⚡ Process & Index Files (Background)",
            type="primary",
            use_container_width=True,
            key="process_files_btn",
        ):
            try:
                job_id = enqueue_ingestion_job(
                    branch_name=st.session_state.active_branch,
                    uploaded_files=uploaded_files,
                )
                st.session_state.uploader_key += 1
                st.toast("🚀 Ingestion task started in background! You can continue using SnowWiki.", icon="⚡")
                st.rerun()
            except Exception as exc:
                st.error(f"❌ Ingestion Error: {exc}")

    # Render reactive task status monitor
    render_active_ingestion_jobs(st.session_state.active_branch)

    st.divider()

    # ── Session Files & Summaries ──────────────────────────────────────────
    st.markdown("### ℹ️ Session Files")
    active_state = load_branch_state(st.session_state.active_branch)
    files_info   = active_state.get("files", {})

    if not files_info:
        st.caption("No files indexed yet.")
    else:
        for fname, finfo in files_info.items():
            icon = "🎬" if finfo.get("type") == "media" else "📄"
            with st.expander(f"{icon} {fname}"):
                st.caption(f"**Type:** {finfo.get('type', 'file').upper()}")
                summary_text = finfo.get('summary', 'No summary.')
                st.markdown(f"**Summary:**\n{summary_text}")

                if st.button(f"🔄 Retry Summary for {fname}", key=f"retry_{fname}"):
                    from src.transcriber import generate_file_summary, transcribe_media_groq, save_branch_state
                    from src.ingestion.core import extract_document_text

                    file_type = finfo.get("type", "document")
                    save_path = finfo.get("path")

                    if save_path and os.path.exists(save_path):
                        with st.spinner(f"Retrying summary for {fname}..."):
                            file_text = ""
                            if file_type == "media":
                                file_text, _ = transcribe_media_groq(save_path, st.session_state.active_branch, fname)
                            else:
                                ext = os.path.splitext(save_path)[1].lower()
                                file_text = extract_document_text(save_path, ext)

                            new_summary = generate_file_summary(file_text, fname, "Media" if file_type == "media" else "Document")
                            active_state["files"][fname]["summary"] = new_summary
                            save_branch_state(st.session_state.active_branch, active_state)
                        st.rerun()

    st.divider()

    # ── Memory & Master Summary ────────────────────────────────────────────
    mem_ctx     = memory_manager.get_condensed_context(st.session_state.active_branch, st.session_state.active_session_id)
    run_summary = mem_ctx.get("running_summary", "")
    if run_summary:
        with st.expander("🧠 This Session's Memory"):
            st.markdown(run_summary)

    master_sum = active_state.get("master_summary", "")
    with st.expander("👑 Master Branch Summary"):
        if master_sum:
            st.markdown(master_sum)
            if st.button("🔄 Retry Master Summary"):
                from src.transcriber import update_master_branch_summary
                with st.spinner("Retrying..."):
                    update_master_branch_summary(st.session_state.active_branch)
                st.rerun()
        else:
            st.caption("Upload files to generate a master branch summary.")

    # Phase 4: Active Learning & Feedback Analytics
    try:
        from src.feedback_store import get_feedback_metrics
        from src.config import VECTOR_STORE_BACKEND
        metrics = get_feedback_metrics(st.session_state.active_branch)
        with st.expander("📊 RAG Quality & Audit", expanded=False):
            st.markdown(f"**Vector DB:** `Qdrant ({VECTOR_STORE_BACKEND.upper()})`")
            st.markdown(f"**Satisfaction Rate:** `{metrics['satisfaction_rate']}% 👍` ({metrics['thumbs_up']} up / {metrics['thumbs_down']} down)")
            if metrics["hard_negatives_count"] > 0:
                st.info(f"📁 **Curated Gaps:** `{metrics['hard_negatives_count']}` queries saved to `data/eval/hard_negatives.json` for continuous training.")
    except Exception:
        pass


# ── Main Chat Area ─────────────────────────────────────────────────────────────
active_branch = st.session_state.active_branch

# Header card
st.markdown(
    f"""
<div class="snow-header">
    <div class="snow-title">❄️ SnowWiki Smart Routing AI</div>
    <div class="snow-subtitle">
        Enterprise ServiceNow Knowledge Agent &nbsp;|&nbsp;
        Active Branch: <span class="snow-branch-pill">{active_branch}</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# Routing legend
st.markdown(
    """
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px;">
  <span class="badge badge-greeting">⚡ Small LLM (Greeting)</span>
  <span class="badge badge-conv">💬 Conversational (Memory)</span>
  <span class="badge badge-rag">🔍 Local RAG + 70B LLM</span>
  <span class="badge badge-overview">📋 Branch Overview</span>
  <span class="badge badge-web">🌐 Google Search Fallback</span>
  <span class="badge badge-outscope">⛔ Out of Scope</span>
</div>
""",
    unsafe_allow_html=True,
)

# ── Render Chat History ────────────────────────────────────────────────────────
branch_msgs: list[dict] = st.session_state.messages

for msg_idx, msg in enumerate(branch_msgs):
    with st.chat_message(msg["role"]):
        # Routing badge (assistant messages only)
        if msg.get("badge_class") and msg.get("badge"):
            st.markdown(
                f'<span class="badge {msg["badge_class"]}">{msg["badge"]}</span>',
                unsafe_allow_html=True,
            )

        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            render_answer_with_images(
                msg["content"],
                branch_name=active_branch,
                image_manifest=msg.get("image_manifest") or {},
            )

            render_source_chunks(msg.get("retrieved_chunks", []))
            render_media_reference(msg)
            render_web_sources(msg.get("grounding_sources", []) if msg.get("source_type") == "web_grounding" else [])

            if msg.get("pipeline_trace"):
                render_pipeline_trace(msg["pipeline_trace"])

            # Thumbs-up / Thumbs-down feedback for assistant responses
            query_id = msg.get("query_id") or f"hist_{msg_idx}"
            fb_key = f"fb_{query_id}_{msg_idx}"
            user_fb = st.feedback("thumbs", key=fb_key)
            if user_fb is not None and not msg.get("_feedback_given"):
                fb_type = "thumbs_up" if user_fb == 1 else "thumbs_down"
                try:
                    from src.feedback_store import record_feedback
                    record_feedback(
                        query_id=query_id,
                        query_text=msg.get("user_query", ""),
                        answer_text=msg["content"],
                        feedback=fb_type,
                        branch=active_branch,
                        stage_used=msg.get("badge", ""),
                        candidate_trace=msg.get("candidate_trace"),
                    )
                    msg["_feedback_given"] = True
                    st.toast(f"Recorded {fb_type.replace('_', ' ')}! Added to evaluation dataset.", icon="✅")
                except Exception as fb_exc:
                    pass

# Vision Debug viewer — shows Qwen-VL extractions for active branch
render_vision_debug_viewer(active_branch)

# ── Chat Input & Processing ───────────────────────────────────────────────────
user_query = st.chat_input(
    "Ask about ServiceNow configurations, workflows, modules, scripting…",
    key="chat_input",
)

if user_query:
    if not groq_ok:
        st.error("⚠️ No LLM backend configured. Set GROQ_API_KEY or USE_LOCAL_LLM=true in .env.")
    else:
        # 1. Append & display user message
        user_msg = {"role": "user", "content": user_query}
        st.session_state.messages.append(user_msg)
        memory_manager.add_message(active_branch, st.session_state.active_session_id, user_msg)

        with st.chat_message("user"):
            st.markdown(user_query)

        # 2. Pull condensed memory context
        memory_context = memory_manager.get_condensed_context(active_branch, st.session_state.active_session_id)

        # 3. Run Smart Routing pipeline
        with st.chat_message("assistant"):
            with st.spinner("🧠 Classifying intent…"):
                result = query_snow_wiki(
                    query_text=user_query,
                    active_branch=active_branch,
                    memory_context=memory_context,
                )

            # Badge
            badge       = result.get("badge", "")
            badge_class = result.get("badge_class", "")
            if badge and badge_class:
                st.markdown(
                    f'<span class="badge {badge_class}">{badge}</span>',
                    unsafe_allow_html=True,
                )

            # Legacy index warning
            if result.get("legacy_index"):
                st.warning(
                    "⚠️ This branch was indexed with the old chunking system. "
                    "Re-upload files to enable Parent-Child RAG and richer source references."
                )

            answer_text    = result.get("answer", result.get("response", "No answer generated."))
            image_manifest = result.get("image_manifest") or {}
            render_answer_with_images(answer_text, branch_name=active_branch, image_manifest=image_manifest)

            # Source chunks + media + web sources for live response
            retrieved_chunks = result.get("retrieved_chunks", [])
            render_source_chunks(retrieved_chunks)
            render_media_reference(result)
            if result.get("source_type") == "web_grounding":
                render_web_sources(result.get("grounding_sources", []))

            # Render Pipeline Trace for current live response
            pipeline_trace = result.get("pipeline_trace")
            if pipeline_trace:
                render_pipeline_trace(pipeline_trace)

        # 4. Persist assistant message
        assistant_msg = {
            "role":              "assistant",
            "content":           answer_text,
            "badge":             badge,
            "badge_class":       badge_class,
            "source_type":       result.get("source_type"),
            "top_chunk":         result.get("top_chunk"),
            "source_file":       result.get("source_file"),
            "timestamp":         result.get("timestamp"),
            "timestamp_seconds": result.get("timestamp_seconds"),
            "media_path":        result.get("media_path"),
            "grounding_sources": result.get("grounding_sources"),
            "retrieved_chunks":  retrieved_chunks,
            "pipeline_trace":    pipeline_trace,
            "image_manifest":    image_manifest,
            "query_id":          result.get("query_id"),
            "user_query":        user_query,
            "candidate_trace":   result.get("candidate_trace"),
        }
        st.session_state.messages.append(assistant_msg)
        memory_manager.add_message(active_branch, st.session_state.active_session_id, assistant_msg)

        # 5. Background memory compaction (every 10 messages)
        memory_manager.check_and_summarize_history(active_branch, st.session_state.active_session_id)
        st.rerun()
