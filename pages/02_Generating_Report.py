import os
import streamlit as st
import time
from datetime import datetime, timedelta
from app.ui import inject_base_styles, top_nav, theme_provider
try:
    import requests
except Exception:
    requests = None
from streamlit_extras.switch_page_button import switch_page


 
 
# Helper: read webhook URL from session/env or use default test URL
def _n8n_webhook_url() -> str:
    if "n8n_webhook_url" in st.session_state and st.session_state["n8n_webhook_url"]:
        # Normalize any stale host to the new IP automatically
        val = st.session_state["n8n_webhook_url"].strip()
        if "34.238.174.186" in val:
            val = val.replace("34.238.174.186", "35.153.104.117")
            st.session_state["n8n_webhook_url"] = val
        return val
    return os.getenv("N8N_WEBHOOK_URL", "http://35.153.104.117:5678/webhook-test/af770afa-01a0-4cda-b95f-4cc94a920691")

def _set_n8n_webhook_url(url: str) -> None:
    st.session_state["n8n_webhook_url"] = (url or "").strip()

def _post_with_retries(url: str, payload: dict, attempts: int = 1, timeout: int = 30) -> tuple[int, str]:
    if requests is None:
        return (0, "requests not available")
    last_err = None
    # Normalize any stale host to the new IP automatically
    if "34.238.174.186" in url:
        url = url.replace("34.238.174.186", "35.153.104.117")
    for i in range(attempts):
        try:
            headers = {"Content-Type": "application/json"}
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            return (resp.status_code, resp.text)
        except Exception as e:
            last_err = str(e)
            time.sleep(min(1 + i, 3))
    return (0, last_err or "unknown error")

def _trigger_webhook(url: str, payload: dict, attempts: int = 1, timeout: int = 30) -> tuple[int, str, str]:
    status, text = _post_with_retries(url, payload, attempts=attempts, timeout=timeout)
    # Treat read timeouts as accepted (many n8n webhooks process asynchronously)
    if status == 0 and isinstance(text, str) and "timed out" in text.lower():
        return 202, text, url
    # If test endpoint isn't registered, fall back to prod
    if status == 404 and text and "not registered" in text.lower() and "/webhook-test/" in url:
        prod_url = url.replace("/webhook-test/", "/webhook/")
        status, text = _post_with_retries(prod_url, payload, attempts=attempts, timeout=timeout)
        return status, text, prod_url
    # If prod endpoint isn't registered (or 404), try test endpoint
    if status == 404 and "/webhook/" in url and "/webhook-test/" not in url:
        test_url = url.replace("/webhook/", "/webhook-test/")
        status, text = _post_with_retries(test_url, payload, attempts=attempts, timeout=timeout)
        return status, text, test_url
    return status, text, url


def _extract_version_from_response(text: str) -> str | None:
    try:
        import json as _json
        data = _json.loads(text)
        # Handle shapes: { codeVersion: "..." } or [ { "Version": "..." } ]
        if isinstance(data, dict):
            val = data.get("codeVersion") or data.get("version") or data.get("Version")
            if isinstance(val, str):
                return val
        if isinstance(data, list) and data:
            cand = data[0]
            if isinstance(cand, dict):
                val = cand.get("codeVersion") or cand.get("version") or cand.get("Version")
                if isinstance(val, str):
                    return val
    except Exception:
        return None
    return None


def _extract_ai_signed_url(text: str) -> tuple[str | None, str | None]:
    """Return (signed_url, key_basename) if present in webhook response array."""
    try:
        import json as _json
        data = _json.loads(text)
        if isinstance(data, list) and data:
            d0 = data[0]
            if isinstance(d0, dict):
                url = d0.get("signed_url") or d0.get("url")
                key = d0.get("key") or d0.get("s3_path") or ""
                base = (key.split("/")[-1] if isinstance(key, str) and key else None)
                return (url, base)
    except Exception:
        return (None, None)
    return (None, None)


def ensure_authenticated() -> bool:
    if st.session_state.get("authentication_status") is True:
        return True
    st.warning("Please login to access this page.")
    st.stop()


def main() -> None:
    st.set_page_config(page_title="Generating Report+", page_icon="⏳", layout="wide")
    theme_provider()
    inject_base_styles()
    top_nav()
    
    ensure_authenticated()
 
    # --- Query params / state
    params = st.query_params if hasattr(st, "query_params") else {}
    url_start = params.get("start", ["0"])[0] == "1"
    case_id = (st.session_state.get("last_case_id") or params.get("case_id", [""])[0]).strip() or "0000"

    # Ensure single-fire per case: keep a per-case guard
    if "__webhook_fired__" not in st.session_state:
        st.session_state["__webhook_fired__"] = {}
    fired_map = st.session_state["__webhook_fired__"]
    # Throttle guard: do not fire more often than once per 60s per case
    if "__webhook_last_fired_ts__" not in st.session_state:
        st.session_state["__webhook_last_fired_ts__"] = {}
    last_ts_map = st.session_state["__webhook_last_fired_ts__"]
 
    # n8n settings (runtime configurable; no debug)
    with st.expander("n8n settings", expanded=False):
        current_url = _n8n_webhook_url()
        new_url = st.text_input("Webhook URL", value=current_url)
        if st.button("Save URL"):
            _set_n8n_webhook_url(new_url)
    # Show last webhook status if present (lightweight)
    if st.session_state.get("last_webhook_status") is not None:
        lw_status = st.session_state.get("last_webhook_status")
        lw_text = st.session_state.get("last_webhook_text") or ""
        if lw_status and 200 <= int(lw_status) < 300:
            st.info(f"Webhook OK (status {lw_status})")
        else:
            st.warning(f"Webhook result: status {lw_status} | {lw_text[:180]}")

    # Initialize session state for progress tracking
    if "generation_progress" not in st.session_state:
        st.session_state["generation_progress"] = 0
    if "generation_step" not in st.session_state:
        st.session_state["generation_step"] = 0
    if "generation_complete" not in st.session_state:
        st.session_state["generation_complete"] = False
    if "generation_start" not in st.session_state:
        st.session_state["generation_start"] = datetime.now()
    if "generation_end" not in st.session_state:
        st.session_state["generation_end"] = None
    if "processing_seconds" not in st.session_state:
        st.session_state["processing_seconds"] = 0
    if "last_completed_case_id" not in st.session_state:
        st.session_state["last_completed_case_id"] = None
 
    # Single-source trigger: URL start=1 OR nav_to_generating flag
    triggered = url_start or st.session_state.pop("nav_to_generating", False)
    
    # Check if this is a new case ID (different from last completed case)
    last_completed_case = st.session_state.get("last_completed_case_id")
    is_new_case = case_id != last_completed_case
    
    # Check throttle window
    now_ts = time.time()
    last_ts = last_ts_map.get(case_id) or 0
    within_window = (now_ts - last_ts) < 60
    if triggered and (not fired_map.get(case_id)) and (not within_window):
        st.session_state["generation_in_progress"] = True
        # Reset progress when starting fresh (new case or first time)
        st.session_state["generation_progress"] = 0
        st.session_state["generation_step"] = 0
        st.session_state["generation_complete"] = False
        st.session_state["generation_start"] = datetime.now()
        st.session_state["generation_end"] = None
        st.session_state["processing_seconds"] = 0
        # Trigger n8n webhook non-blocking, no debug
        try:
            url = _n8n_webhook_url()
            status, text, final_url = _trigger_webhook(url, {"case_id": case_id}, attempts=1, timeout=10)
            st.session_state["last_webhook_status"] = status
            st.session_state["last_webhook_text"] = (text or "")[:300]
            # Mark as fired for this case to avoid duplicate triggers
            fired_map[case_id] = True
            st.session_state["__webhook_fired__"] = fired_map
            last_ts_map[case_id] = now_ts
            st.session_state["__webhook_last_fired_ts__"] = last_ts_map
            # Capture code version from webhook response if present
            ver = _extract_version_from_response(text)
            if ver:
                if ver.endswith('.json'):
                    ver = ver[:-5]
                st.session_state["code_version"] = ver
                by_case = st.session_state.get("code_version_by_case", {})
                by_case[str(case_id)] = ver
                st.session_state["code_version_by_case"] = by_case
            # Capture AI signed URL for immediate Results viewing
            ai_url, ai_label = _extract_ai_signed_url(text)
            if ai_url:
                by_case_ai = st.session_state.get("ai_signed_url_by_case", {})
                by_case_ai[str(case_id)] = ai_url
                st.session_state["ai_signed_url_by_case"] = by_case_ai
                by_case_label = st.session_state.get("ai_label_by_case", {})
                by_case_label[str(case_id)] = (ai_label or "AI Report")
                st.session_state["ai_label_by_case"] = by_case_label
            if final_url != url:
                _set_n8n_webhook_url(final_url)
        except Exception:
            pass
        try:
            qp = st.query_params if hasattr(st, "query_params") else None
            if qp is not None:
                qp["start"] = "0"
                qp["case_id"] = case_id
        except Exception:
            pass
 
    if not st.session_state.get("generation_in_progress"):
        # st.markdown('<div class="section-bg" style="max-width:900px;margin:0 auto;text-align:centermake;">', unsafe_allow_html=True)
        st.markdown("<h3>Generating Report</h3>", unsafe_allow_html=True)
        new_id = st.text_input("Enter Case ID (4 digits)", value=case_id)
        start_click = st.button("Start", type="primary")
        if start_click and not fired_map.get(new_id or case_id):
            st.session_state["last_case_id"] = (new_id or case_id).strip()
            st.session_state["generation_in_progress"] = True
            st.session_state["generation_progress"] = 0
            st.session_state["generation_step"] = 0
            st.session_state["generation_complete"] = False
            st.session_state["generation_start"] = datetime.now()
            st.session_state["generation_end"] = None
            st.session_state["processing_seconds"] = 0
            # Trigger n8n webhook on manual start (no debug)
            cid = st.session_state.get("last_case_id") or case_id
            try:
                url = _n8n_webhook_url()
                status, text, final_url = _trigger_webhook(url, {"case_id": cid}, attempts=1, timeout=10)
                st.session_state["last_webhook_status"] = status
                st.session_state["last_webhook_text"] = (text or "")[:300]
                fired_map[cid] = True
                st.session_state["__webhook_fired__"] = fired_map
                last_ts_map[cid] = time.time()
                st.session_state["__webhook_last_fired_ts__"] = last_ts_map
                ver = _extract_version_from_response(text)
                if ver:
                    if ver.endswith('.json'):
                        ver = ver[:-5]
                    st.session_state["code_version"] = ver
                    by_case = st.session_state.get("code_version_by_case", {})
                    by_case[str(cid)] = ver
                    st.session_state["code_version_by_case"] = by_case
                if final_url != url:
                    _set_n8n_webhook_url(final_url)
                # Capture AI signed URL for immediate Results viewing
                ai_url, ai_label = _extract_ai_signed_url(text)
                if ai_url:
                    by_case_ai = st.session_state.get("ai_signed_url_by_case", {})
                    by_case_ai[str(cid)] = ai_url
                    st.session_state["ai_signed_url_by_case"] = by_case_ai
                    by_case_label = st.session_state.get("ai_label_by_case", {})
                    by_case_label[str(cid)] = (ai_label or "AI Report")
                    st.session_state["ai_label_by_case"] = by_case_label
            except Exception:
                pass
            try:
                qp = st.query_params if hasattr(st, "query_params") else None
                if qp is not None:
                    qp["case_id"] = st.session_state["last_case_id"]
                    qp["start"] = "0"
            except Exception:
                pass
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return
 
    case_id = st.session_state.get("last_case_id", params.get("case_id", ["UNKNOWN"])[0])
    start_time = st.session_state["generation_start"]
 
    st.markdown('<div class="section-bg" style="max-width:900px;margin:0 auto;">', unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
    st.markdown("""
        <div style='font-size:32px'>☕</div>
        <h3>Generating Your Report</h3>
        <p style='opacity:.9;margin-top:-6px;'>Hey there, Doctor! ☕ Why not grab a coffee while we work our magic? Your comprehensive report is being crafted with care, and we'll email you the results as soon as it's ready!</p>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
 
    progress = st.progress(st.session_state["generation_progress"])
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
 
    # Update step status based on current progress
    current_step = st.session_state["generation_step"]
    for i in range(len(steps)):
        if i < current_step:
            line(i, "done")
        elif i == current_step:
            line(i, "active")
        else:
            line(i, "waiting")
 
    # Only run progress animation if not complete and we're in progress, or if it's a new case
    if (not st.session_state["generation_complete"] and st.session_state.get("generation_in_progress")) or is_new_case:
        # Demo mode: simulate progress without external dependencies
        n8n_ph.info(f"🔄 Generating report for Case ID: {case_id}")
        
        # Continue from where we left off
        current_progress = st.session_state["generation_progress"]
        current_step = st.session_state["generation_step"]
        
        # Simple progress animation - continue from current state
        for i in range(current_progress, 100):
            st.session_state["generation_progress"] = i + 1
            progress.progress(i + 1)
            
            # Update step status as we progress
            if i < 20:
                st.session_state["generation_step"] = 0
                line(0, "active")
            elif i < 40:
                st.session_state["generation_step"] = 1
                line(0, "done")
                line(1, "active")
            elif i < 60:
                st.session_state["generation_step"] = 2
                line(1, "done")
                line(2, "active")
            elif i < 80:
                st.session_state["generation_step"] = 3
                line(2, "done")
                line(3, "active")
            elif i < 95:
                st.session_state["generation_step"] = 4
                line(3, "done")
                line(4, "active")
            else:
                st.session_state["generation_step"] = 4
                line(4, "done")
            
            time.sleep(0.03)  # Faster progress for demo
        
        # Mark as complete
        st.session_state["generation_complete"] = True
        st.session_state["generation_end"] = datetime.now()
        st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - start_time).total_seconds())
        n8n_ph.success(f"✅ Report generation complete for Case ID: {case_id}!")
    elif st.session_state["generation_complete"]:
        # Show completion status if already done
        n8n_ph.success(f"✅ Report generation complete for Case ID: {case_id}!")
    
    # End info section
    end_time = st.session_state["generation_end"] or datetime.now()
    processing_seconds = st.session_state["processing_seconds"]
 
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
            st.caption("ELAPSED TIME")
            st.write(f"{processing_seconds // 60}m {processing_seconds % 60}s")
            st.info("We will email you upon completion with the download link.")
    
    # Clean demo completion - no external workflow status needed
    
    st.markdown('</div>', unsafe_allow_html=True)
 
    st.markdown("<div style='text-align:center;margin-top:.5rem;'>", unsafe_allow_html=True)
    if st.button("View Results", type="primary"):
        # Prefer programmatic navigation with fallbacks
        tried = False
        for label in [
            "04_Results",
            "Results",
            "Results Page",
            "Results+",
        ]:
            try:
                switch_page(label)
                tried = True
                break
            except Exception:
                continue
        # Fallback: update query params and inject client redirect
        if not tried:
            try:
                qp = st.query_params if hasattr(st, "query_params") else None
                if qp is not None:
                    qp["page"] = "04_Results"
                    qp["case_id"] = case_id
            except Exception:
                pass
            st.markdown(
                f"""
                <script>
                  const params = new URLSearchParams(window.location.search);
                  params.set('page', '04_Results');
                  params.set('case_id', '{case_id}');
                  window.location.search = '?' + params.toString();
                </script>
                """,
                unsafe_allow_html=True,
            )
        st.stop()
    st.markdown("</div>", unsafe_allow_html=True)
 
 
main()