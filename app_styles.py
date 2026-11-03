"""
app_styles.py
=============
CSS injection for the SnowWiki Streamlit app.

Call inject_css() once at app startup (before any st.markdown / widget calls)
to apply the full premium dark-mode design system.
"""

import streamlit as st


def inject_css() -> None:
    """Inject the SnowWiki premium dark-mode CSS into the Streamlit app."""
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
.badge-overview {
    background: rgba(246,173,85,0.18);
    color: #f6ad55;
    border: 1px solid rgba(246,173,85,0.4);
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
