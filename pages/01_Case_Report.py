import streamlit as st
import time
import random
import os
import requests
from datetime import datetime
from app.ui import inject_base_styles, show_header, top_nav, hero_section, feature_grid, footer_section, theme_provider
import os
import requests
from streamlit_extras.switch_page_button import switch_page


def ensure_authenticated() -> bool:
    if st.session_state.get("authentication_status") is True:
        return True
    st.warning("Please login to access this page.")
    st.stop()


def main() -> None:
    st.set_page_config(page_title="Case Report", page_icon="📄", layout="wide")
    theme_provider()
    inject_base_styles()
    top_nav()
    hero_section(
        title="Generate Case Report",
        description=(
            "Enter your Case ID below to generate a comprehensive report with "
            "detailed analysis and insights."
        ),
        icon="🗂️",
    )

    ensure_authenticated()
    
    # Check if generation is already in progress
    if st.session_state.get("generation_in_progress", False):
        st.markdown("## Case Report Generation")
        st.markdown(
            """
            <div style="text-align: center; padding: 2rem 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; margin: 1rem 0; max-width: 600px; margin-left: auto; margin-right: auto;">
                <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">⏳</div>
                <h3 style="color: white; margin-bottom: 0.5rem; font-weight: 600;">Report Generation in Progress</h3>
                <p style="color: rgba(255,255,255,0.9); font-size: 0.95rem; margin-bottom: 1rem;">
                    You are already generating a report. If you want to generate another report, you can proceed and the previous report will be saved to the History page.
                </p>
                <div style="display: flex; justify-content: center; margin-top: 1rem;">
                    <div style="width: 30px; height: 30px; border: 3px solid rgba(255,255,255,0.3); border-top: 3px solid white; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                </div>
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        # Show current generation info
        current_case = st.session_state.get("current_case_id", "Unknown")
        generation_start = st.session_state.get("generation_start")
        if generation_start:
            from datetime import datetime
            elapsed = datetime.now() - generation_start
            elapsed_minutes = int(elapsed.total_seconds() / 60)
            st.info(f"🔄 Currently generating report for Case ID: **{current_case}** (Running for {elapsed_minutes} minutes)")
        
        # Option to continue with new report
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("---")
            st.markdown("**Want to generate another report?**")
            if st.button("Generate New Report", type="secondary", use_container_width=True):
                # Clear ALL generation-related state to ensure clean reset
                st.session_state["generation_in_progress"] = False
                st.session_state["generation_complete"] = False
                st.session_state["generation_failed"] = False
                st.session_state["generation_timeout"] = False
                st.session_state["generation_progress"] = 0
                st.session_state["generation_step"] = 0
                st.session_state["generation_start"] = None
                st.session_state["generation_end"] = None
                st.session_state["processing_seconds"] = 0
                st.session_state["current_case_id"] = None
                st.session_state["last_completed_case_id"] = None
                
                # Clear webhook-related state
                st.session_state.pop("last_webhook_status", None)
                st.session_state.pop("last_webhook_text", None)
                
                # Clear fired flags for all cases to allow fresh start
                st.session_state["__webhook_fired__"] = {}
                st.session_state["__webhook_last_fired_ts__"] = {}
                
                # Clear navigation flag
                st.session_state.pop("nav_to_generating", None)
                
                st.rerun()
        
        return
    
    # Backend base URL
    params = st.query_params if hasattr(st, "query_params") else {}
    BACKEND_BASE = (
        params.get("api", [None])[0]
        or os.getenv("BACKEND_BASE")
        or "http://100.24.25.37"
    ).rstrip("/")

    # Create centered form with same width as info box below
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.caption("Case ID (4 digits)")
        case_id = st.text_input("Enter 4-digit Case ID (e.g., 1234)", key="case_id", max_chars=4)
        
        # Real-time validation feedback
        if case_id:
            if not case_id.isdigit():
                st.error("⚠️ Case ID must contain only digits (0-9)")
            elif len(case_id) != 4:
                st.warning(f"⚠️ Case ID must be exactly 4 digits (current: {len(case_id)})")
            else:
                st.success("✅ Valid Case ID format")
        
        # Show current user info
        username = st.session_state.get("username") or st.session_state.get("name")
        if username:
            st.info(f"👤 Logged in as: {username}")
        else:
            st.warning("⚠️ No username found - reports will use 'demo' user")
        
        generate = st.button("Generate Report", type="primary", use_container_width=True)
        if generate:
            cid = case_id.strip()
            if not cid or not cid.isdigit() or len(cid) != 4:
                st.error("Case ID must be exactly 4 digits (0-9).")
            else:
                st.session_state["last_case_id"] = cid
                from datetime import datetime
                st.session_state["generation_start"] = datetime.now()
                st.session_state["generation_in_progress"] = True
                st.session_state["nav_to_generating"] = True
                
                # Ensure username is available
                if not username:
                    username = "demo"
                
                # Store case ID for S3 fetching in results page
                st.session_state["current_case_id"] = cid
                st.session_state["username"] = username
                
                # External workflow temporarily disabled; proceed with S3-only flow
                webhook_success = True
                
                # Create a simple backend cycle for this user and case (legacy support)
                try:
                    r = requests.post(
                        f"{BACKEND_BASE}/cycles",
                        json={"username": username, "case_id": cid, "status": "processing"},
                        timeout=8,
                    )
                    if r.ok:
                        st.session_state["current_cycle_id"] = r.json().get("id")
                except Exception:
                    pass
                
                # Pass case/report ids via URL as well for robustness
                try:
                    qp = st.query_params if hasattr(st, "query_params") else None
                    if qp is not None:
                        qp["case_id"] = cid
                except Exception:
                    pass
                # Set URL params first so the target page reads start=1 deterministically
                try:
                    qp = st.query_params if hasattr(st, "query_params") else None
                    if qp is not None:
                        qp["page"] = "02_Generating_Report"
                        qp["case_id"] = cid
                        qp["start"] = "1"
                except Exception:
                    pass
                # Navigate to Generating Report page
                try:
                    switch_page("Generating_Report")
                except Exception:
                    st.experimental_set_query_params(page="02_Generating_Report", case_id=cid, start="1")
                    st.rerun()
                st.stop()

    # Subtle info card beneath the form
    with st.container():
        st.markdown(
            """
            <div class="section-bg fade-in" style="max-width:900px;margin:0.75rem auto 0 auto;text-align:center;">
              <span style="opacity:.9;">Report generation takes approximately 2 hours to complete.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Footer intentionally omitted on Case Report page


if __name__ == "__main__":
    main()


