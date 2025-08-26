import streamlit as st
import time
import random
from datetime import datetime
from app.ui import inject_base_styles, show_header, top_nav, hero_section, feature_grid, footer_section, theme_provider
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

    with st.container():
        st.markdown('<div class="section-bg slide-up" style="max-width:900px;margin:0 auto;">', unsafe_allow_html=True)
        st.caption("Case ID (4 digits)")
        case_id = st.text_input("Enter 4-digit Case ID (e.g., 1234)", key="case_id")
        c_left, c_center, c_right = st.columns([1, 1, 1])
        with c_center:
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
                # Pass case/report ids via URL as well for robustness
                try:
                    st.experimental_set_query_params(case_id=cid)
                except Exception:
                    pass
                # Set URL params first so the target page reads start=1 deterministically
                try:
                    st.experimental_set_query_params(page="02_Generating_Report", case_id=cid, start="1")
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
        st.markdown("</div>", unsafe_allow_html=True)

    # Subtle info card beneath the form
    with st.container():
        st.markdown(
            """
            <div class="section-bg fade-in" style="max-width:900px;margin:0.75rem auto 0 auto;text-align:center;">
              <span style="opacity:.9;">Report generation typically takes 30–60 seconds to complete.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center'>", unsafe_allow_html=True)
    st.subheader("Comprehensive Case Analysis")
    st.caption("Our platform provides detailed insights and analytics for every case.")
    st.markdown("</div>", unsafe_allow_html=True)

    feature_grid([
        ("🕒", "Real-time Processing", "Get instant access to case data and real-time updates as information becomes available."),
        ("🛡️", "Secure & Compliant", "Enterprise-grade security with full compliance to industry standards and regulations."),
        ("⬇️", "Export Options", "Download reports in multiple formats including PDF, Excel, and CSV for easy sharing."),
    ])

    footer_section()


if __name__ == "__main__":
    main()


