import os
import streamlit as st
import time
from datetime import datetime, timedelta
from app.ui import inject_base_styles, top_nav, theme_provider
try:
    import requests
except Exception:
    requests = None
 
 
def main() -> None:
    st.set_page_config(page_title="Generating Report+", page_icon="⏳", layout="wide")
    theme_provider()
    inject_base_styles()
    top_nav()
 
    # --- Query params / state
    params = st.experimental_get_query_params()
    url_start = params.get("start", ["0"])[0] == "1"
    case_id = (st.session_state.get("last_case_id") or params.get("case_id", [""])[0]).strip() or "0000"
 
    # Single-source trigger: URL start=1 OR nav_to_generating flag
    triggered = url_start or st.session_state.pop("nav_to_generating", False)
    if triggered:
        st.session_state["generation_in_progress"] = True
        st.experimental_set_query_params(**{**params, "start": "0", "case_id": case_id})
 
    if not st.session_state.get("generation_in_progress"):
        st.markdown('<div class="section-bg" style="max-width:900px;margin:0 auto;text-align:center;">', unsafe_allow_html=True)
        st.markdown("<h3>Generating Report</h3>", unsafe_allow_html=True)
        new_id = st.text_input("Enter Case ID (4 digits)", value=case_id)
        start_click = st.button("Start", type="primary")
        if start_click:
            st.session_state["last_case_id"] = (new_id or case_id).strip()
            st.session_state["generation_in_progress"] = True
            st.experimental_set_query_params(case_id=st.session_state["last_case_id"], start="0")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return
 
    case_id = st.session_state.get("last_case_id", params.get("case_id", ["UNKNOWN"])[0])
    start_time = st.session_state.get("generation_start", datetime.now())
    st.session_state["generation_start"] = start_time
 
    st.markdown('<div class="section-bg" style="max-width:900px;margin:0 auto;">', unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
    st.markdown("""
        <div style='font-size:32px'>📄</div>
        <h3>Generating Report</h3>
        <p style='opacity:.9;margin-top:-6px;'>Grab a coffee while we generate your report. We will email you as soon as it's complete.</p>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
 
    progress = st.progress(0)
    n8n_ph = st.empty()
    st.markdown("""
        <div style="display:flex;justify-content:space-between;margin-top:4px;padding:0 4px;">
          <span style="opacity:.8;">0%</span>
          <span style="opacity:.8;padding-right:2px;">100%</span>
        </div>
    """, unsafe_allow_html=True)
 
    steps = [
        "Validating case ID",
        "Fetching data",
        "Compiling report",
        "Finalizing",
        "Preparing download",
    ]
    placeholders = [st.empty() for _ in steps]
 
    def line(idx: int, state: str):
        icon = {"waiting": "○", "active": "⏳", "done": "✅"}[state]
        style = {
            "waiting": "opacity:.8;",
            "active": "font-weight:600;",
            "done": "opacity:.9; text-decoration: line-through;",
        }[state]
        placeholders[idx].markdown(f"- {icon} <span style='{style}'>{steps[idx]}...</span>", unsafe_allow_html=True)
 
    for i in range(len(steps)):
        line(i, "waiting")
 
    # For now, we'll simulate the report generation process
    # Later this will be replaced with actual n8n integration
    st.session_state["__simulation_fired_for__"] = case_id
    st.session_state["__simulation_fired_at__"] = datetime.now()
 
    pct = 0
    durations = [12, 12, 14, 10, 10]
    for i, d in enumerate(durations):
        line(i, "active")
        target = int(((i + 1) / len(durations)) * 100)
        for _ in range(d * 5):
            pct = min(target, pct + max(1, (target - pct) // 4))
            progress.progress(pct)
 
            # Show simulation status
            fired_at = st.session_state.get("__simulation_fired_at__")
            if fired_at and (datetime.now() - fired_at).total_seconds() >= 10:
                n8n_ph.success(f"Report generation simulation active for Case ID: {case_id}")
            time.sleep(0.2)
        line(i, "done")
 
    # End info section
    end_time = datetime.now()
    st.session_state["generation_end"] = end_time
    st.session_state["processing_seconds"] = int((end_time - start_time).total_seconds())
 
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="section-bg">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("STARTED")
            st.write(start_time.strftime("%b %d, %Y %I:%M %p").lstrip('0'))
        with c2:
            st.caption("FINISHED")
            st.write(end_time.strftime("%b %d, %Y %I:%M %p").lstrip('0'))
        with c3:
            seconds = st.session_state.get("processing_seconds", 0)
            st.caption("ELAPSED TIME")
            st.write(f"{seconds // 60}m {seconds % 60}s")
        st.info("We will email you upon completion with the download link.")
        st.markdown('</div>', unsafe_allow_html=True)
 
    st.markdown("<div style='text-align:center;margin-top:.5rem;'>", unsafe_allow_html=True)
    if st.button("View Results", type="primary"):
        st.experimental_set_query_params(page="Results", case_id=case_id)
        st.markdown(
            f"""
            <script>
              const params = new URLSearchParams(window.location.search);
              params.set('page', 'Results');
              params.set('case_id', '{case_id}');
              window.location.search = '?' + params.toString();
            </script>
            """,
            unsafe_allow_html=True,
        )
        st.stop()
    st.markdown("</div>", unsafe_allow_html=True)
 
 
main()