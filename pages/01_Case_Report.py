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
    # Backend base URL
    params = st.query_params if hasattr(st, "query_params") else {}
    BACKEND_BASE = (
        params.get("api", [None])[0]
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
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
                # Try several labels that might match the page entry
                tried = False
                for label in [
                    "02_Generating_Report",
                    "Generating_Report",
                    "Generating Report+",
                    "Generating Report",
                ]:
                    try:
                        switch_page(label)
                        tried = True
                        break
                    except Exception:
                        continue
                # Fallback to client-side redirect
                if not tried:
                    st.markdown(
                        f"""
                        <script>
                          const params = new URLSearchParams(window.location.search);
                          params.set('page', '02_Generating_Report');
                          params.set('case_id', '{cid}');
                          params.set('start', '1');
                          window.location.search = '?' + params.toString();
                        </script>
                        """,
                        unsafe_allow_html=True,
                    )
                st.stop()

    # Subtle info card beneath the form
    with st.container():
        st.markdown(
            """
            <div class="section-bg fade-in" style="max-width:900px;margin:0.75rem auto 0 auto;text-align:center;">
              <span style="opacity:.9;">Report generation typically takes 25 - 30 minutes to complete.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    footer_section()


if __name__ == "__main__":
    main()


