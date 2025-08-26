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

    # Determine start conditions and case id
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

    # Resolve webhook URL without touching st.secrets (avoid missing-secrets warning)
    webhook_url = params.get("n8n", [""])[0]
    if not webhook_url:
        webhook_url = "http://3.82.11.141:5678/webhook-test/c55f207e-1edb-4f10-9c5a-13648ccef428"
    # Fire webhook once (short timeout) and remember when we did so
    if not st.session_state.get("__n8n_fired__"):
        st.session_state["__n8n_fired__"] = True
        st.session_state["__n8n_fired_at__"] = datetime.now()
        if requests and webhook_url:
            try:
                resp = requests.post(webhook_url, json={"case_id": case_id}, timeout=4)
                st.session_state["__n8n_resp__"] = {
                    "status": getattr(resp, "status_code", None),
                    "ok": getattr(resp, "ok", None),
                    "text": (getattr(resp, "text", "") or "")[:200],
                }
            except Exception as e:
                st.session_state["__n8n_resp__"] = {"error": str(e)}

    pct = 0
    durations = [12, 12, 14, 10, 10]
    for i, d in enumerate(durations):
        line(i, "active")
        target = int(((i + 1) / len(durations)) * 100)
        for _ in range(d * 5):
            pct = min(target, pct + max(1, (target - pct) // 4))
            progress.progress(pct)
            resp_info = st.session_state.get("__n8n_resp__")
            if resp_info and isinstance(resp_info, dict):
                if "error" in resp_info:
                    n8n_ph.error(f"n8n webhook error: {resp_info['error']}")
                elif resp_info.get("status") is not None:
                    n8n_ph.info(f"n8n status: {resp_info.get('status')} • ok={resp_info.get('ok')} • {resp_info.get('text','')}")
            fired_at = st.session_state.get("__n8n_fired_at__")
            if fired_at and (datetime.now() - fired_at).total_seconds() >= 10:
                n8n_ph.success(f"n8n linked. Echo: {case_id}")
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


