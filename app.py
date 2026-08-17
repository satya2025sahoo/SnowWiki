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
"""

from __future__ import annotations

import os
from datetime import datetime
import time

import streamlit as st
from dotenv import load_dotenv

# ── Load .env secrets before anything else ────────────────────────────────────
load_dotenv()

# ── Backend imports ────────────────────────────────────────────────────────────
from src.config import PROJECT_STATES_DIR, GROQ_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID, USE_LOCAL_LLM
from src.transcriber import load_branch_state
from src.ingestion import process_and_ingest_files
from src.retriever import query_snow_wiki
from src.memory import MemoryManager
from src.tracing import init_tracing

# ── Initialize LangSmith tracing (no-op if LANGSMITH_API_KEY is absent) ──────────
init_tracing()

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SnowWiki | Smart Routing AI",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Premium Dark CSS ──────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global reset ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background: linear-gradient(135deg, #0a0d14 0%, #0f1520 50%, #0d1117 100%);
    color: #e2e8f0;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    border-right: 1px solid rgba(99,179,237,0.15);
}
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #90cdf4;
    letter-spacing: 0.5px;
}

/* ── New Chat button ── */
.new-chat-btn > button {
    background: linear-gradient(135deg, #2d6a9f 0%, #4299e1 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.5px;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 15px rgba(66,153,225,0.35) !important;
}
.new-chat-btn > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(66,153,225,0.55) !important;
}

/* ── Session History Buttons ── */
.session-btn-active > button {
    border-left: 4px solid #63b3ed !important;
    background: rgba(99,179,237,0.1) !important;
    color: #63b3ed !important;
}

/* ── Process Files button ── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #2f855a 0%, #48bb78 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 12px rgba(72,187,120,0.3) !important;
}

/* ── Chat header card ── */
.snow-header {
    background: rgba(16, 22, 35, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(99,179,237,0.2);
    border-radius: 16px;
    padding: 22px 28px;
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(99,179,237,0.05);
}
.snow-title {
    font-size: 1.9rem;
    font-weight: 700;
    background: linear-gradient(90deg, #63b3ed 0%, #b794f4 60%, #f687b3 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 4px 0;
    letter-spacing: -0.5px;
}
.snow-subtitle {
    color: #718096;
    font-size: 0.9rem;
    margin: 0;
}
.snow-branch-pill {
    display: inline-block;
    background: rgba(99,179,237,0.15);
    color: #63b3ed;
    border: 1px solid rgba(99,179,237,0.3);
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.82rem;
    font-weight: 600;
    margin-left: 6px;
    vertical-align: middle;
}

/* ── Status indicator row ── */
.status-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}
.status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    display: inline-block;
}
.status-online  { background: #68d391; box-shadow: 0 0 6px #68d391; }
.status-warn    { background: #f6ad55; box-shadow: 0 0 6px #f6ad55; }
.status-offline { background: #fc8181; box-shadow: 0 0 6px #fc8181; }
.status-label {
    font-size: 0.78rem;
    color: #718096;
    font-weight: 500;
}

/* ── Routing Badges ── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 0.82rem;
    font-weight: 600;
    margin-bottom: 10px;
    letter-spacing: 0.2px;
}
.badge-greeting {
    background: rgba(104,211,145,0.18);
    color: #68d391;
    border: 1px solid rgba(104,211,145,0.4);
}
.badge-rag {
    background: rgba(99,179,237,0.18);
    color: #63b3ed;
    border: 1px solid rgba(99,179,237,0.4);
}
.badge-web {
    background: rgba(246,173,85,0.18);
    color: #f6ad55;
    border: 1px solid rgba(246,173,85,0.4);
}
.badge-outscope {
    background: rgba(252,129,129,0.18);
    color: #fc8181;
    border: 1px solid rgba(252,129,129,0.4);
}
.badge-conv {
    background: rgba(183,148,244,0.18);
    color: #b794f4;
    border: 1px solid rgba(183,148,244,0.4);
}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
    background: rgba(22, 30, 46, 0.6) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 14px !important;
    margin-bottom: 10px !important;
    backdrop-filter: blur(4px);
    padding: 14px 18px !important;
    transition: border-color 0.2s;
}
[data-testid="stChatMessage"]:hover {
    border-color: rgba(99,179,237,0.2) !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] textarea {
    background: rgba(22, 30, 46, 0.9) !important;
    border: 1px solid rgba(99,179,237,0.25) !important;
    border-radius: 14px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: rgba(99,179,237,0.6) !important;
    box-shadow: 0 0 0 3px rgba(99,179,237,0.1) !important;
}

/* ── Sidebar file card ── */
.file-card {
    background: rgba(22, 30, 46, 0.8);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 0.85rem;
}

/* ── Divider color ── */
hr { border-color: rgba(255,255,255,0.08) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #2d3748; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4a5568; }
</style>
""",
    unsafe_allow_html=True,
)

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
        dt = datetime.fromisoformat(dt_str)
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
    except:
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
            s_id = s.get("id")
            title = s.get("title", "New Chat")
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
                    st.session_state.active_branch = clean
                    st.session_state.active_session_id = memory_manager.create_session(clean)
                    st.session_state.messages = []
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
        st.session_state.active_branch = selected_branch
        # Start fresh session for the newly selected branch
        st.session_state.active_session_id = memory_manager.create_session(selected_branch)
        st.session_state.messages = []
        st.rerun()

    st.divider()

    # ── File Uploader ──────────────────────────────────────────────────────
    st.markdown(f"### 📤 Upload to `{st.session_state.active_branch}`")
    uploaded_files = st.file_uploader(
        "Select training media or docs:",
        type=["mp4", "mkv", "mp3", "pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Supported: .mp4 .mkv .mp3 .pdf .docx .txt",
        key="file_uploader",
    )

    if uploaded_files:
        if st.button(
            "⚡ Process & Index Files",
            type="primary",
            use_container_width=True,
            key="process_files_btn",
        ):
            status_ph  = st.empty()
            progress   = st.progress(0)

            def _status(msg: str) -> None:
                status_ph.info(f"⏳ {msg}")

            try:
                process_and_ingest_files(
                    branch_name=st.session_state.active_branch,
                    file_objects=uploaded_files,
                    status_callback=_status,
                )
                progress.progress(100)
                status_ph.success("✅ Ingestion & Indexing Complete!")
                st.rerun()
            except Exception as exc:
                status_ph.error(f"❌ Ingestion Error: {exc}")

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
                st.markdown(f"**Summary:**\n{finfo.get('summary', 'No summary.')}")

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
        else:
            st.caption("Upload files to generate a master branch summary.")


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
  <span class="badge badge-web">🌐 Google Search Fallback</span>
  <span class="badge badge-outscope">⛔ Out of Scope</span>
</div>
""",
    unsafe_allow_html=True,
)

# ── Render Chat History ────────────────────────────────────────────────────────
branch_msgs: list[dict] = st.session_state.messages

for msg in branch_msgs:
    with st.chat_message(msg["role"]):
        # Routing badge (assistant messages only)
        if msg.get("badge_class") and msg.get("badge"):
            st.markdown(
                f'<span class="badge {msg["badge_class"]}">{msg["badge"]}</span>',
                unsafe_allow_html=True,
            )

        st.markdown(msg["content"])

        # Visual Vector Inspection Box
        if msg.get("retrieved_chunks"):
            with st.expander("📄 View Referenced Vector Chunks & Page/Timestamp Sources", expanded=False):
                for idx, chunk in enumerate(msg["retrieved_chunks"], 1):
                    page_time = chunk.get("page_or_timestamp") or chunk.get("page") or chunk.get("timestamp") or "N/A"
                    score_val = chunk.get("score") if chunk.get("score") is not None else chunk.get("similarity_score", "N/A")
                    st.markdown(
                        f"**Chunk #{idx}** | 📁 **Source:** `{chunk.get('source', 'Unknown')}` | "
                        f"📖 **Page/Time:** `{page_time}` | "
                        f"🎯 **Similarity:** `{score_val}`"
                    )
                    st.info(chunk.get("chunk_text", ""))

        # Video / Audio timestamp reference
        if (
            msg.get("source_type") == "internal"
            and msg.get("media_path")
            and os.path.exists(msg["media_path"])
        ):
            st.markdown("---")
            st.markdown(
                f"**🎥 Source:** `{msg.get('source_file')}` @ `{msg.get('timestamp')}`"
            )
            ext = os.path.splitext(msg["media_path"])[1].lower()
            start_sec = msg.get("timestamp_seconds", 0)
            if ext in {".mp4", ".mkv"}:
                st.video(msg["media_path"], start_time=start_sec)
            elif ext == ".mp3":
                st.audio(msg["media_path"], start_time=start_sec)

            with st.expander("🔍 Raw Transcript Chunk"):
                st.code(msg.get("top_chunk", ""))

        # Web fallback sources
        if msg.get("source_type") == "web_grounding" and msg.get("grounding_sources"):
            st.markdown("---")
            st.markdown("**🌐 Sources:**")
            for src in msg["grounding_sources"]:
                st.markdown(f"- [{src.get('title', 'ServiceNow Docs')}]({src.get('url', '#')})")


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
            route_labels = {
                "greeting":    "⚡ Routing via Small LLM…",
                "conversational": "💬 Checking session memory…",
                "out_of_scope": "⛔ Checking scope…",
                "local_rag":   "🔍 Searching local knowledge base…",
                "web_fallback": "🌐 Falling back to Google Search…",
            }
            spinner_msg = "🧠 Classifying intent…"

            with st.spinner(spinner_msg):
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
                
            if "stage_used" in result and "Polish" in result["stage_used"]:
                st.caption("✨ *Response refined by Polish LLM*")

            answer_text = result.get("answer", result.get("response", "No answer generated."))
            st.markdown(answer_text)

            # Visual Vector Inspection Box for Live Response
            retrieved_chunks = result.get("retrieved_chunks", [])
            if retrieved_chunks:
                with st.expander("📄 View Referenced Vector Chunks & Page/Timestamp Sources", expanded=False):
                    for idx, chunk in enumerate(retrieved_chunks, 1):
                        page_time = chunk.get("page_or_timestamp") or chunk.get("page") or chunk.get("timestamp") or "N/A"
                        score_val = chunk.get("score") if chunk.get("score") is not None else chunk.get("similarity_score", "N/A")
                        st.markdown(
                            f"**Chunk #{idx}** | 📁 **Source:** `{chunk.get('source', 'Unknown')}` | "
                            f"📖 **Page/Time:** `{page_time}` | "
                            f"🎯 **Similarity:** `{score_val}`"
                        )
                        st.info(chunk.get("chunk_text", ""))

            # Video / Audio reference for local RAG hits
            if (
                result.get("source_type") == "internal"
                and result.get("media_path")
                and os.path.exists(result["media_path"])
            ):
                st.markdown("---")
                st.markdown(
                    f"**🎥 Source:** `{result.get('source_file')}` @ `{result.get('timestamp')}`"
                )
                ext       = os.path.splitext(result["media_path"])[1].lower()
                start_sec = result.get("timestamp_seconds", 0)
                if ext in {".mp4", ".mkv"}:
                    st.video(result["media_path"], start_time=start_sec)
                elif ext == ".mp3":
                    st.audio(result["media_path"], start_time=start_sec)

                with st.expander("🔍 Raw Transcript Chunk"):
                    st.code(result.get("top_chunk", ""))

            # Web sources for fallback hits
            if result.get("source_type") == "web_grounding" and result.get("grounding_sources"):
                st.markdown("---")
                st.markdown("**🌐 Sources:**")
                for src in result["grounding_sources"]:
                    st.markdown(
                        f"- [{src.get('title', 'ServiceNow Docs')}]({src.get('url', '#')})"
                    )

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
        }
        st.session_state.messages.append(assistant_msg)
        memory_manager.add_message(active_branch, st.session_state.active_session_id, assistant_msg)

        # 5. Background memory compaction (every 10 messages)
        memory_manager.check_and_summarize_history(active_branch, st.session_state.active_session_id)
        st.rerun()
