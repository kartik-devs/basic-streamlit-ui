from __future__ import annotations

import streamlit as st


def inject_base_styles() -> None:
    theme = st.session_state.get("theme", "dark")
    if theme == "light":
        bg = "#f8fafc"  # slate-50
        panel = "rgba(0,0,0,0.06)"
        panel_border = "rgba(0,0,0,0.15)"
        accent = "#3b82f6"  # blue-500 for better contrast
        primary = "#1e40af"  # blue-700
        text = "#0f172a"  # slate-900 for readability on light bg
        panel_bg = "#ffffff"
    else:
        bg = "#0f172a"  # slate-900
        panel = "rgba(255,255,255,0.06)"
        panel_border = "rgba(255,255,255,0.12)"
        accent = "#3b82f6"  # blue-500
        primary = "#60a5fa"  # blue-400
        text = "#e5e7eb"  # slate-200 on dark bg
        panel_bg = "rgba(255,255,255,0.04)"

    st.markdown(
        f"""
        <style>
        :root {{
          --bg: {bg};
          --panel: {panel};
          --panel-border: {panel_border};
          --accent: {accent};
          --primary: {primary};
          --text: {text};
          --panel-bg: {panel_bg};
        }}

        body, .stApp {{ 
          background: var(--bg) !important; 
          color: var(--text) !important; 
          transition: background-color 0.3s ease, color 0.3s ease;
        }}
        .markdown-text-container, .stMarkdown, [data-testid="stMarkdownContainer"] {{ 
          color: var(--text) !important; 
          transition: color 0.3s ease;
        }}
        h1, h2, h3, h4, h5, h6, p, span, label {{ 
          color: var(--text); 
          transition: color 0.3s ease;
        }}

        .main .block-container {{padding-top: 2.5rem;}}
        
        .section-bg {{
          background: var(--panel-bg);
          border: 1px solid var(--panel-border);
          border-radius: 14px;
          padding: 1rem 1.25rem 1.25rem 1.25rem;
          box-shadow: 0 6px 20px rgba(0,0,0,0.12);
          position: relative;
          z-index: 0;
          overflow: hidden;
        }}

        /* Tab bar styling */
        .stTabs [data-baseweb="tab-list"] {{
          gap: .5rem;
          background: var(--panel);
          border: 1px solid var(--panel-border);
          border-radius: 12px;
          padding: .35rem;
        }}
        .stTabs [data-baseweb="tab"] {{
          border-radius: 10px;
          padding: .6rem .9rem;
        }}
        .stTabs [aria-selected="true"] {{
          background: rgba(255,255,255,0.08);
          border: 1px solid var(--panel-border);
        }}

        /* Button styling for both themes */
        .stButton > button {{
          background: var(--panel-bg) !important;
          color: var(--text) !important;
          border: 1px solid var(--panel-border) !important;
          transition: all 0.3s ease !important;
        }}
        .stButton > button:hover {{
          background: var(--panel) !important;
          border-color: var(--accent) !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .stButton > button:disabled {{
          opacity: 0.5 !important;
          cursor: not-allowed !important;
        }}
        
        /* Download button styling */
        .stDownloadButton > button {{
          background: var(--panel-bg) !important;
          color: var(--text) !important;
          border: 1px solid var(--panel-border) !important;
          transition: all 0.3s ease !important;
        }}
        .stDownloadButton > button:hover {{
          background: var(--panel) !important;
          border-color: var(--accent) !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        
        /* Theme toggle button styling */
        [data-testid="baseButton-secondary"] {{
          background: var(--panel-bg) !important;
          color: var(--text) !important;
          border: 1px solid var(--panel-border) !important;
          border-radius: 8px !important;
          padding: 8px 12px !important;
          font-size: 16px !important;
          transition: all 0.3s ease !important;
        }}
        [data-testid="baseButton-secondary"]:hover {{
          background: var(--panel) !important;
          border-color: var(--accent) !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}

        .fade-in {{animation: fadeIn .6s ease-out both;}}
        .slide-up {{animation: slideUp .6s ease-out both;}}

        @keyframes fadeIn {{from {{opacity:0;}} to {{opacity:1;}}}}
        @keyframes slideUp {{from {{opacity:0; transform: translateY(18px);}} to {{opacity:1; transform: translateY(0);}} }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def theme_provider() -> None:
    if "theme" not in st.session_state:
        st.session_state["theme"] = "dark"


def show_header(title: str, subtitle: str | None = None, icon: str | None = None) -> None:
    with st.container():
        st.markdown('<div class="fade-in" style="text-align:center;">', unsafe_allow_html=True)
        if icon:
            st.markdown(f"<div style='font-size:42px'>{icon}</div>", unsafe_allow_html=True)
        st.title(title)
        if subtitle:
            st.caption(subtitle)
        st.markdown("</div>", unsafe_allow_html=True)


def _perform_logout() -> None:
    for key in [
        "authentication_status",
        "name",
        "username",
        "last_case_id",
        "generation_start",
        "generation_end",
        "generation_in_progress",
        "processing_seconds",
    ]:
        if key in st.session_state:
            del st.session_state[key]
    # Force logged-out gate until explicit sign-in
    st.session_state["authentication_status"] = False
    st.session_state["__force_logged_out__"] = True
    # Clear auth cookies used by streamlit-authenticator
    st.markdown(
        """
        <script>
          document.cookie = "casetracker_auth=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
          document.cookie = "casetracker_signature=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        </script>
        """,
        unsafe_allow_html=True,
    )
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.session_state["__just_logged_out__"] = True
    st.success("Logged out. Please sign in again to continue.")
    st.rerun()


def top_nav(active: str = "Dashboard") -> None:
    with st.container():
        left, center, right = st.columns([4, 1, 2])
        with left:
            st.markdown(
                """
                <div class="fade-in" style="display:flex;align-items:center;gap:1.25rem;padding:.5rem 0 .75rem 0;">
                  <div style="font-weight:700;">CaseTracker Pro</div>
                  <div style="opacity:.9;display:flex;gap:1rem;font-size:.95rem;">
                    <span>Dashboard</span>
                    <span>Reports</span>
                    <span>Settings</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with center:
            # Theme toggle
            current_theme = st.session_state.get("theme", "dark")
            theme_icon = "🌙" if current_theme == "dark" else "☀️"
            if st.button(theme_icon, key="theme_toggle", help=f"Switch to {'light' if current_theme == 'dark' else 'dark'} mode"):
                st.session_state["theme"] = "light" if current_theme == "dark" else "dark"
                st.rerun()
        with right:
            st.markdown("<div style='height:.25rem'></div>", unsafe_allow_html=True)
            if st.button("Log out", use_container_width=True):
                _perform_logout()
        st.markdown(
            "<hr style=\"opacity:.12;border:none;border-top:1px solid var(--panel-border);margin:0 0 1rem 0;\" />",
            unsafe_allow_html=True,
        )


def hero_section(title: str, description: str, icon: str) -> None:
    st.markdown(
        f"""
        <div class="fade-in" style="text-align:center;margin-top:.5rem;">
          <div style="font-size:40px">{icon}</div>
          <h1 style="margin:0.4rem 0 0.2rem 0;">{title}</h1>
          <p style="opacity:.9;">{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def feature_grid(features: list[tuple[str, str, str]]) -> None:
    cols = st.columns(3)
    for (icon, heading, text), col in zip(features, cols):
        with col:
            st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:26px'>{icon}</div>", unsafe_allow_html=True)
            st.markdown(f"**{heading}**")
            st.caption(text)
            st.markdown("</div>", unsafe_allow_html=True)


def footer_section() -> None:
    st.markdown(
        """
        <div style="margin-top:2rem;">
          <div class="section-bg">
            <div style="display:grid;grid-template-columns:1.2fr 1fr 1fr 1fr;gap:1rem;">
              <div>
                <strong>CaseTracker Pro</strong>
                <div style="opacity:.9;">Professional case management and reporting solution for modern enterprises.</div>
              </div>
              <div>
                <strong>Product</strong>
                <div>Features</div>
                <div>Pricing</div>
                <div>Documentation</div>
              </div>
              <div>
                <strong>Support</strong>
                <div>Help Center</div>
                <div>Contact Us</div>
                <div>Status</div>
              </div>
              <div>
                <strong>Legal</strong>
                <div>Privacy Policy</div>
                <div>Terms of Service</div>
                <div>Security</div>
              </div>
            </div>
            <div style="opacity:.7;text-align:center;margin-top:1rem;">© 2025 CaseTracker Pro. All rights reserved.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


