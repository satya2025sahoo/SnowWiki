import os
import streamlit as st
from dotenv import load_dotenv
from google import genai

# Import modular backend packages
from src.config import PROJECT_STATES_DIR
from src.transcriber import load_branch_state
from src.ingestion import process_and_ingest_files
from src.retriever import query_snow_wiki

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="SNOW Wiki | Enterprise AI Platform",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Enterprise Dark Aesthetics
st.markdown("""
<style>
    /* Dark glassmorphic container styles */
    .main {
        background-color: #0E1117;
    }
    .stApp {
        background: linear-gradient(135deg, #0e1117 0%, #161b22 100%);
        color: #e6edf3;
    }
    
    /* Header Card */
    .snow-header {
        background: rgba(22, 27, 34, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    .snow-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4299E1 0%, #9F7AEA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .snow-subtitle {
        color: #a0aec0;
        font-size: 1.0rem;
        margin-top: 4px;
    }

    /* Status Badges */
    .badge-internal {
        background-color: rgba(72, 187, 120, 0.2);
        color: #68D391;
        border: 1px solid #48BB78;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 12px;
    }
    .badge-web {
        background-color: rgba(236, 201, 75, 0.2);
        color: #F6E05E;
        border: 1px solid #ECC94B;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 12px;
    }

    /* Sidebar Custom Styling */
    .css-1d39125, [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    
    /* File Card in Sidebar */
    .file-card {
        background: #1c2128;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 8px;
        border: 1px solid #30363d;
    }
    
    /* Custom button styling */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
</style>
""", unsafe_allow_html=True)

# State initialization
if "branches" not in st.session_state:
    # Discover existing branches from project_states
    existing_branches = []
    if os.path.exists(PROJECT_STATES_DIR):
        for f in os.listdir(PROJECT_STATES_DIR):
            if f.endswith(".json"):
                existing_branches.append(f[:-5])
    if not existing_branches:
        existing_branches = ["CSM Training", "ITOM Deep Dive", "Weekly Tuesday KT"]
    st.session_state.branches = existing_branches

if "active_branch" not in st.session_state:
    st.session_state.active_branch = st.session_state.branches[0]

if "messages" not in st.session_state:
    st.session_state.messages = {}  # branch -> message list

if st.session_state.active_branch not in st.session_state.messages:
    st.session_state.messages[st.session_state.active_branch] = []

# Sidebar Engine
with st.sidebar:
    st.markdown("## ❄️ SNOW Wiki Engine")
    
    # API Key Handling
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    api_key_input = st.text_input(
        "Google Gemini API Key", 
        value=gemini_key, 
        type="password",
        help="Get your key from Google AI Studio (a free key works)"
    )
    if api_key_input:
        os.environ["GEMINI_API_KEY"] = api_key_input
        
    st.divider()

    # Session / Branch Manager Header
    st.markdown("### 📁 Training Sessions")
    
    # Add Session Button & Input
    col_sel, col_add = st.columns([0.75, 0.25])
    
    with col_add:
        show_add_modal = st.button("➕ New", help="Create a new training branch session")
        
    if show_add_modal:
        st.session_state.show_branch_input = True

    if st.session_state.get("show_branch_input", False):
        new_branch_name = st.text_input("New Branch Name:", placeholder="e.g. SPM Masterclass")
        col_create, col_cancel = st.columns(2)
        with col_create:
            if st.button("Create"):
                if new_branch_name and new_branch_name.strip():
                    clean_name = new_branch_name.strip()
                    if clean_name not in st.session_state.branches:
                        st.session_state.branches.append(clean_name)
                    st.session_state.active_branch = clean_name
                    st.session_state.show_branch_input = False
                    st.rerun()
        with col_cancel:
            if st.button("Cancel"):
                st.session_state.show_branch_input = False
                st.rerun()

    # Branch Selector Dropdown
    selected_branch = st.selectbox(
        "Active Branch:",
        options=st.session_state.branches,
        index=st.session_state.branches.index(st.session_state.active_branch) if st.session_state.active_branch in st.session_state.branches else 0
    )
    if selected_branch != st.session_state.active_branch:
        st.session_state.active_branch = selected_branch
        if selected_branch not in st.session_state.messages:
            st.session_state.messages[selected_branch] = []
        st.rerun()

    st.divider()

    # Multi-file Uploader Section
    st.markdown(f"### 📤 Upload Files (`{st.session_state.active_branch}`)")
    uploaded_files = st.file_uploader(
        "Select training media or docs:",
        type=["mp4", "mkv", "mp3", "pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Upload .mp4, .mkv, .mp3, .pdf, .docx, or .txt"
    )

    if uploaded_files:
        if st.button("⚡ Process & Index Files", type="primary", use_container_width=True):
            if not os.environ.get("GEMINI_API_KEY"):
                st.error("Please enter a valid Gemini API Key above.")
            else:
                client = genai.Client()
                status_placeholder = st.empty()
                progress_bar = st.progress(0)
                
                def update_status(msg):
                    status_placeholder.info(f"⏳ {msg}")

                try:
                    process_and_ingest_files(
                        client=client,
                        branch_name=st.session_state.active_branch,
                        file_objects=uploaded_files,
                        status_callback=update_status
                    )
                    progress_bar.progress(100)
                    status_placeholder.success("✅ Ingestion & Summarization Complete!")
                    st.rerun()
                except Exception as e:
                    status_placeholder.error(f"❌ Ingestion Error: {str(e)}")

    st.divider()

    # Active Session File Manager & Summaries ('ℹ️' Info button per file)
    st.markdown("### ℹ️ Session Files & Summaries")
    active_state = load_branch_state(st.session_state.active_branch)
    files_info = active_state.get("files", {})

    if not files_info:
        st.caption("No files uploaded to this session yet.")
    else:
        for fname, finfo in files_info.items():
            file_type = finfo.get("type", "file")
            icon = "🎬" if file_type == "media" else "📄"
            
            with st.expander(f"{icon} {fname}"):
                st.caption(f"**Type:** {file_type.upper()}")
                st.markdown(f"**Summary:**\n{finfo.get('summary', 'No summary available.')}")

    st.divider()

    # Master Branch Summary Expander
    master_sum = active_state.get("master_summary", "")
    with st.expander("👑 Master Branch Summary"):
        if master_sum:
            st.markdown(master_sum)
        else:
            st.caption("Upload files to generate a master branch summary.")

# Main Application Screen
st.markdown(f"""
<div class="snow-header">
    <div class="snow-title">SNOW Wiki Platform</div>
    <div class="snow-subtitle">Enterprise ServiceNow Training Assistant & Knowledge Engine | Active Session: <strong>{st.session_state.active_branch}</strong></div>
</div>
""", unsafe_allow_html=True)

# Render Chat History for Active Branch
branch_msgs = st.session_state.messages.get(st.session_state.active_branch, [])

for msg in branch_msgs:
    with st.chat_message(msg["role"]):
        if msg.get("badge_html"):
            st.markdown(msg["badge_html"], unsafe_allow_html=True)
            
        st.markdown(msg["content"])

        # Render Video Player if internal match with timestamp seek
        if msg.get("source_type") == "internal" and msg.get("media_path") and os.path.exists(msg["media_path"]):
            st.markdown("---")
            st.markdown(f"**🎥 Video Timestamp Reference:** `{msg.get('source_file')}` @ `[{msg.get('timestamp')}]`")
            start_sec = msg.get("timestamp_seconds", 0)
            
            ext = os.path.splitext(msg["media_path"])[1].lower()
            if ext in [".mp4", ".mkv"]:
                st.video(msg["media_path"], start_time=start_sec)
            elif ext == ".mp3":
                st.audio(msg["media_path"], start_time=start_sec)

            with st.expander("🔍 View Raw Transcript Chunk"):
                st.code(msg.get("top_chunk", ""))

        # Render Grounding Sources if Web Fallback
        if msg.get("source_type") == "web_grounding" and msg.get("grounding_sources"):
            st.markdown("---")
            st.markdown("**🌐 ServiceNow Live Documentation Sources:**")
            for src in msg["grounding_sources"]:
                st.markdown(f"- [{src.get('title', 'ServiceNow Docs')}]({src.get('url', '#')})")

# Chat Input & Processing Engine
user_query = st.chat_input("Ask a technical question about ServiceNow configurations, workflows, or code...")

if user_query:
    if not os.environ.get("GEMINI_API_KEY"):
        st.warning("⚠️ Please provide a Gemini API Key in the sidebar to run queries.")
    else:
        # Append User Message
        branch_msgs.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # Process Query with AI Engine
        with st.chat_message("assistant"):
            with st.spinner("🔍 Hierarchical Search (Master Summary -> Video Summaries -> Granular Vector DB)..."):
                client = genai.Client()
                result = query_snow_wiki(
                    client=client,
                    query_text=user_query,
                    active_branch=st.session_state.active_branch
                )

            # Construct Result UI
            answer_text = result["answer"]
            badge_html = ""

            if result["found"]:
                sim_pct = int(result["similarity"] * 100)
                badge_html = f'<div class="badge-internal">🎯 Internal Match ({sim_pct}% Similarity) | {result["stage_used"]}</div>'
                st.markdown(badge_html, unsafe_allow_html=True)
                st.markdown(answer_text)

                if result.get("media_path") and os.path.exists(result["media_path"]):
                    st.markdown("---")
                    st.markdown(f"**🎥 Video Timestamp Reference:** `{result.get('source_file')}` @ `[{result.get('timestamp')}]`")
                    start_sec = result.get("timestamp_seconds", 0)
                    
                    ext = os.path.splitext(result["media_path"])[1].lower()
                    if ext in [".mp4", ".mkv"]:
                        st.video(result["media_path"], start_time=start_sec)
                    elif ext == ".mp3":
                        st.audio(result["media_path"], start_time=start_sec)

                    with st.expander("🔍 View Raw Transcript Chunk"):
                        st.code(result.get("top_chunk", ""))

            else:
                sim_pct = int(result["similarity"] * 100)
                badge_html = f'<div class="badge-web">🌐 Topic not found in internal videos (Similarity: {sim_pct}%). Referencing live ServiceNow documentation...</div>'
                st.markdown(badge_html, unsafe_allow_html=True)
                st.markdown(answer_text)

                if result.get("grounding_sources"):
                    st.markdown("---")
                    st.markdown("**🌐 ServiceNow Live Documentation Sources:**")
                    for src in result["grounding_sources"]:
                        st.markdown(f"- [{src.get('title', 'ServiceNow Docs')}]({src.get('url', '#')})")

            # Save Assistant Response to Session History
            assistant_msg = {
                "role": "assistant",
                "content": answer_text,
                "badge_html": badge_html,
                "source_type": result["source_type"],
                "top_chunk": result.get("top_chunk"),
                "source_file": result.get("source_file"),
                "timestamp": result.get("timestamp"),
                "timestamp_seconds": result.get("timestamp_seconds"),
                "media_path": result.get("media_path"),
                "grounding_sources": result.get("grounding_sources")
            }
            branch_msgs.append(assistant_msg)
            st.session_state.messages[st.session_state.active_branch] = branch_msgs
