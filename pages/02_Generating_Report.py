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

# Backend base URL resolver
def _get_backend_base() -> str:
    params = st.query_params if hasattr(st, "query_params") else {}
    return (
        (params.get("api", [None])[0] if isinstance(params.get("api"), list) else params.get("api"))
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
    ).rstrip("/")

# Check if case exists in S3 via backend
def _case_exists(case_id: str) -> bool:
    if not requests:
        return True  # Do not block when requests missing
    try:
        backend = _get_backend_base()
        r = requests.get(f"{backend}/s3/cases", timeout=8)
        if r.ok:
            data = r.json() or {}
            cases = data.get("cases") or []
            return str(case_id) in {str(c) for c in cases}
    except Exception:
        return False
    return False

 
 
# Helper: read webhook URL from session/env or use default test URL
def _n8n_webhook_url() -> str:
    if "n8n_webhook_url" in st.session_state and st.session_state["n8n_webhook_url"]:
        # Normalize any stale host to the new IP automatically
        val = st.session_state["n8n_webhook_url"].strip()
        if "34.238.174.186" in val:
            val = val.replace("34.238.174.186", "35.153.104.117")
            st.session_state["n8n_webhook_url"] = val
        return val
    return os.getenv("N8N_WEBHOOK_URL", "http://3.81.112.43:5678/webhook/af770afa-01a0-4cda-b95f-4cc94a920691")

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
                # Support direct field or nested under pdf/docx
                url = (
                    d0.get("signed_url")
                    or d0.get("url")
                    or (isinstance(d0.get("pdf"), dict) and d0.get("pdf").get("signed_url"))
                    or (isinstance(d0.get("docx"), dict) and d0.get("docx").get("signed_url"))
                )
                key = (
                    d0.get("key")
                    or d0.get("s3_path")
                    or (isinstance(d0.get("pdf"), dict) and d0.get("pdf").get("key"))
                    or (isinstance(d0.get("docx"), dict) and d0.get("docx").get("key"))
                    or ""
                )
                base = (key.split("/")[-1] if isinstance(key, str) and key else None)
                return (url, base)
    except Exception:
        return (None, None)
    return (None, None)


def _extract_runtime_metrics(text: str) -> dict:
    """Parse webhook JSON for metrics like ocr_start_time/ocr_end_time and token usage.
    Returns a dict with keys: ocr_start_time, ocr_end_time, total_tokens_used, total_input_tokens, total_output_tokens,
    docx_url, pdf_url.
    """
    out: dict = {}
    try:
        import json as _json
        data = _json.loads(text)
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict):
                continue
            # nested artifacts
            if isinstance(it.get("docx"), dict):
                out["docx_url"] = it["docx"].get("signed_url") or it["docx"].get("url")
            if isinstance(it.get("pdf"), dict):
                out["pdf_url"] = it["pdf"].get("signed_url") or it["pdf"].get("url")
            # top-level metrics
            for k in [
                "ocr_start_time",
                "ocr_end_time",
                "total_tokens_used",
                "total_input_tokens",
                "total_output_tokens",
            ]:
                if it.get(k) is not None:
                    out[k] = it.get(k)
    except Exception:
        return {}
    return out


def _poll_n8n_webhook(case_id: str, webhook_url: str) -> dict:
    """Poll n8n webhook for completion data by making a GET request to check status."""
    try:
        import requests
        # Try to get status from n8n webhook (some webhooks support GET for status)
        # This is a fallback - the main data should come from the initial POST response
        response = requests.get(webhook_url.replace("/webhook/", "/webhook-status/"), timeout=5)
        if response.ok:
            return response.json()
    except Exception:
        pass
    return {}


def _check_webhook_completion(case_id: str) -> dict:
    """Check if webhook has completion data by looking at the stored response."""
    # Get the stored webhook response from session state
    webhook_text = st.session_state.get("last_webhook_text", "")
    if not webhook_text:
        return {}
    
    # Extract metrics from the stored response
    metrics = _extract_runtime_metrics(webhook_text)
    
    # Check if we have completion indicators
    has_artifacts = bool(metrics.get("docx_url") or metrics.get("pdf_url"))
    has_end_time = bool(metrics.get("ocr_end_time"))
    has_tokens = bool(metrics.get("total_tokens_used"))
    
    if has_artifacts and has_end_time and has_tokens:
        return metrics
    
    return {}


def _poll_workflow_status(case_id: str) -> dict:
    """Poll n8n workflow status to detect completion, cancellation, or errors."""
    if not requests:
        return {}
    
    try:
        # Use the actual n8n status endpoint
        status_url = f"http://3.82.11.141:5678/webhook-test/workflow-status?case_id={case_id}"
        
        response = requests.get(status_url, timeout=5)
        if response.ok:
            data = response.json()
            return {
                "status": data.get("status", "unknown"),  # running, completed, cancelled, failed
                "message": data.get("message", ""),
                "progress": data.get("progress", 0),
                "error": data.get("error", ""),
                "cancelled": data.get("cancelled", False),
                "completed": data.get("completed", False)
            }
    except Exception as e:
        # If status endpoint doesn't exist or fails, return empty dict
        # This is expected for workflows that don't support status polling
        pass
    
    return {}


def _check_workflow_cancellation(case_id: str) -> bool:
    """Check if workflow was cancelled externally and update UI state accordingly."""
    status = _poll_workflow_status(case_id)
    
    if status.get("cancelled") or status.get("status") == "cancelled":
        # Workflow was cancelled externally
        st.session_state["generation_cancelled"] = True
        st.session_state["generation_in_progress"] = False
        st.session_state["generation_end"] = datetime.now()
        if st.session_state.get("generation_start"):
            st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - st.session_state["generation_start"]).total_seconds())
        return True
    
    if status.get("completed") or status.get("status") == "completed":
        # Workflow completed - extract any completion data
        if status.get("message"):
            # Try to parse completion data from status response
            try:
                import json
                completion_data = json.loads(status.get("message", "{}"))
                metrics = _extract_runtime_metrics(json.dumps(completion_data))
                if metrics:
                    st.session_state.setdefault("webhook_metrics_by_case", {})[str(case_id)] = metrics
            except:
                pass
        
        # Mark as complete
        st.session_state["generation_progress"] = 100
        st.session_state["generation_step"] = 4
        st.session_state["generation_complete"] = True
        st.session_state["generation_in_progress"] = False
        st.session_state["generation_end"] = datetime.now()
        if st.session_state.get("generation_start"):
            st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - st.session_state["generation_start"]).total_seconds())
        return True
    
    if status.get("status") == "failed" or status.get("error"):
        # Workflow failed
        st.session_state["generation_failed"] = True
        st.session_state["generation_in_progress"] = False
        st.session_state["generation_end"] = datetime.now()
        if st.session_state.get("generation_start"):
            st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - st.session_state["generation_start"]).total_seconds())
        return True
    
    return False


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
 
    # n8n settings and webhook status removed for cleaner UI

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
        # Validate case ID against S3 list
        if not _case_exists(case_id):
            st.error(f"Case ID {case_id} not found. Please verify the ID and try again.")
            st.session_state["generation_in_progress"] = False
            return
        # Begin generation and reset state
        st.session_state["generation_in_progress"] = True
        st.session_state["generation_progress"] = 0
        st.session_state["generation_step"] = 0
        st.session_state["generation_complete"] = False
        st.session_state["generation_failed"] = False
        st.session_state["generation_timeout"] = False
        st.session_state["generation_cancelled"] = False
        st.session_state["generation_start"] = datetime.now()
        st.session_state["generation_end"] = None
        st.session_state["processing_seconds"] = 0
        # Clear any stale webhook/completion state
        st.session_state.pop("last_webhook_status", None)
        st.session_state.pop("last_webhook_text", None)
        # Nudge: mark validation complete immediately
        st.session_state["generation_step"] = 1
        st.session_state["generation_progress"] = 5
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
            # Parse runtime metrics and mark complete immediately when present
            metrics = _extract_runtime_metrics(text)
            # Consider run "complete" only when BOTH artifacts AND explicit end time are present
            has_artifacts = bool(
                metrics.get("docx_url")
                or metrics.get("pdf_url")
                or _extract_ai_signed_url(text)[0]
            )
            has_end = bool(metrics.get("ocr_end_time"))
            # Additional check: ensure the webhook response indicates actual completion
            response_complete = "error" not in text.lower() and "invalid" not in text.lower()
            if metrics and has_artifacts and has_end and response_complete:
                st.session_state.setdefault("webhook_metrics_by_case", {})[str(case_id)] = metrics
                st.session_state["generation_progress"] = 100
                st.session_state["generation_step"] = 4
                st.session_state["generation_complete"] = True
                st.session_state["generation_in_progress"] = False
                st.session_state["generation_end"] = datetime.now()
                # Best-effort compute processing seconds if we have times; else wall clock
                try:
                    from dateutil import parser as _dtp  # optional
                    beg = _dtp.parse(metrics.get("ocr_start_time")) if metrics.get("ocr_start_time") else None
                    end = _dtp.parse(metrics.get("ocr_end_time")) if metrics.get("ocr_end_time") else None
                    if beg and end:
                        st.session_state["processing_seconds"] = int((end - beg).total_seconds())
                    else:
                        st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - st.session_state["generation_start"]).total_seconds())
                except Exception:
                    st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - st.session_state["generation_start"]).total_seconds())
            # Do not auto-complete on 2xx alone; wait for explicit completion indicators
        except Exception:
            pass
        try:
            qp = st.query_params if hasattr(st, "query_params") else None
            if qp is not None:
                qp["start"] = "0"
                qp["case_id"] = case_id
        except Exception:
            pass
 
    # Helper to reset state for retry without page reload
    def _reset_generation_state(cid: str) -> None:
        st.session_state["generation_in_progress"] = False
        st.session_state["generation_complete"] = False
        st.session_state["generation_progress"] = 0
        st.session_state["generation_step"] = 0
        st.session_state["generation_start"] = datetime.now()
        st.session_state["generation_end"] = None
        st.session_state["processing_seconds"] = 0
        # Clear fired flag and last webhook response for this case
        try:
            fm = st.session_state.get("__webhook_fired__", {})
            if cid in fm:
                del fm[cid]
            st.session_state["__webhook_fired__"] = fm
        except Exception:
            pass
        st.session_state.pop("last_webhook_status", None)
        st.session_state.pop("last_webhook_text", None)
    
    # Check if no case has been selected yet (case_id is 0000)
    if case_id == "0000":
        st.markdown("## Generating Report")
        st.markdown(
            """
            <div style="text-align: center; padding: 3rem 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; margin: 2rem 0;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">⏳</div>
                <h2 style="color: white; margin-bottom: 1rem; font-weight: 600;">Ready to Generate Reports</h2>
                <p style="color: rgba(255,255,255,0.9); font-size: 1.1rem; margin-bottom: 2rem; max-width: 500px; margin-left: auto; margin-right: auto;">
                    Please go to Case Report first to select a case, then come back here to generate your comprehensive medical report.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Add cute Streamlit button for navigation
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("✨ Go to Case Report →", type="primary", use_container_width=True):
                try:
                    switch_page("Case_Report")
                except Exception:
                    st.info("Please use the sidebar to navigate to 'Case Report'.")
        return

    if not st.session_state.get("generation_in_progress"):
        # st.markdown('<div class="section-bg" style="max-width:900px;margin:0 auto;text-align:centermake;">', unsafe_allow_html=True)
        st.markdown("<h3>Generating Report</h3>", unsafe_allow_html=True)
        
        # Add navigation button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("← Go to Case Report", type="secondary", use_container_width=True):
                try:
                    switch_page("Case_Report")
                except Exception:
                    st.info("Please use the sidebar to navigate to 'Case Report'.")
        
        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        
        new_id = st.text_input("Enter Case ID (4 digits)", value=case_id)
        start_click = st.button("Start", type="primary")
        if start_click and not fired_map.get(new_id or case_id):
            st.session_state["last_case_id"] = (new_id or case_id).strip()
            # Validate before starting
            if not _case_exists(st.session_state["last_case_id"]):
                st.error(f"Case ID {st.session_state['last_case_id']} not found. Please verify the ID and try again.")
                return
            # Begin generation and reset state
            st.session_state["generation_in_progress"] = True
            st.session_state["generation_progress"] = 0
            st.session_state["generation_step"] = 0
            st.session_state["generation_complete"] = False
            st.session_state["generation_failed"] = False
            st.session_state["generation_timeout"] = False
            st.session_state["generation_cancelled"] = False
            st.session_state["generation_start"] = datetime.now()
            st.session_state["generation_end"] = None
            st.session_state["processing_seconds"] = 0
            # Clear any stale webhook/completion state
            st.session_state.pop("last_webhook_status", None)
            st.session_state.pop("last_webhook_text", None)
            # Nudge: mark validation complete immediately
            st.session_state["generation_step"] = 1
            st.session_state["generation_progress"] = 5
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
 
    # Simple header without the big purple section
    st.markdown("## Generating Your Report")
    st.markdown("Your comprehensive medical report is being crafted with advanced AI technology. This process typically takes 60-90 minutes to complete.")
 
    # Bigger progress display
    progress_value = st.session_state["generation_progress"]
    st.markdown(f"""
        <div style="text-align: center; margin: 2rem 0;">
            <div style="font-size: 5rem; font-weight: 700; color: var(--accent); margin-bottom: 0.5rem;">{progress_value}%</div>
            <div style="font-size: 1.2rem; color: var(--text); font-weight: 600;">Progress</div>
        </div>
    """, unsafe_allow_html=True)
    
    n8n_ph = st.empty()
 
    # Modern steps with better icons and styling
    steps = [
        ("Validating case ID", "🔍"),
        ("Fetching medical data", "📊"),
        ("AI analysis in progress", "🤖"),
        ("Generating report", "📝"),
        ("Finalizing & quality check", "✨"),
    ]
    placeholders = [st.empty() for _ in steps]

    def line(idx: int, state: str):
        step_name, step_icon = steps[idx]
        if state == "waiting":
            icon = "○"
            style = "opacity: 0.5; color: var(--text);"
            bg_style = "background: rgba(255,255,255,0.05);"
        elif state == "active":
            icon = "⏳"
            style = "font-weight: 600; color: var(--accent);"
            bg_style = "background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.3);"
        else:  # done
            icon = "✅"
            style = "color: #10b981; font-weight: 500;"
            bg_style = "background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3);"
        
        placeholders[idx].markdown(f"""
            <div style="display: flex; align-items: center; padding: 0.75rem 1rem; margin: 0.5rem 0; border-radius: 8px; {bg_style}">
                <span style="font-size: 1.2rem; margin-right: 0.75rem;">{icon}</span>
                <span style="font-size: 1.1rem; margin-right: 0.5rem;">{step_icon}</span>
                <span style="{style}">{step_name}</span>
            </div>
        """, unsafe_allow_html=True)
 
    # Update step status based on current progress
    current_step = st.session_state["generation_step"]
    for i in range(len(steps)):
        if i < current_step:
            line(i, "done")
        elif i == current_step:
            line(i, "active")
        else:
            line(i, "waiting")
 
    # Check for webhook completion data and update status accordingly
    webhook_completion = _check_webhook_completion(case_id)
    if webhook_completion and not st.session_state.get("generation_complete"):
        # Webhook has completion data - mark as complete immediately
        st.session_state["generation_progress"] = 100
        st.session_state["generation_step"] = 4
        st.session_state["generation_complete"] = True
        st.session_state["generation_in_progress"] = False
        st.session_state["generation_end"] = datetime.now()
        st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - start_time).total_seconds())
        
        # Store the webhook metrics for Results page
        st.session_state.setdefault("webhook_metrics_by_case", {})[str(case_id)] = webhook_completion
        
        # Update AI signed URL for immediate Results viewing
        if webhook_completion.get("docx_url"):
            by_case_ai = st.session_state.get("ai_signed_url_by_case", {})
            by_case_ai[str(case_id)] = webhook_completion["docx_url"]
            st.session_state["ai_signed_url_by_case"] = by_case_ai
            by_case_label = st.session_state.get("ai_label_by_case", {})
            by_case_label[str(case_id)] = "AI Report (DOCX)"
            st.session_state["ai_label_by_case"] = by_case_label
        elif webhook_completion.get("pdf_url"):
            by_case_ai = st.session_state.get("ai_signed_url_by_case", {})
            by_case_ai[str(case_id)] = webhook_completion["pdf_url"]
            st.session_state["ai_signed_url_by_case"] = by_case_ai
            by_case_label = st.session_state.get("ai_label_by_case", {})
            by_case_label[str(case_id)] = "AI Report (PDF)"
            st.session_state["ai_label_by_case"] = by_case_label
        
        # Force rerun to show completion immediately
        st.rerun()


    # Check for cancelled state and display appropriate message
    if st.session_state.get("generation_cancelled"):
        n8n_ph.markdown(f"""
            <div style="background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%); color: white; padding: 1.5rem; border-radius: 12px; text-align: center; margin: 1rem 0;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">⏹️</div>
                <h3 style="color: white; margin: 0; font-weight: 600;">Report Generation Cancelled</h3>
                <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;">Case ID: <strong>{case_id}</strong></p>
                <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0; font-size: 0.9rem;">The workflow was cancelled externally or by the system.</p>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Start New Generation", type="primary", use_container_width=True):
                # Reset cancelled state and restart
                st.session_state["generation_cancelled"] = False
                st.session_state["generation_in_progress"] = True
                st.session_state["generation_progress"] = 0
                st.session_state["generation_step"] = 0
                st.session_state["generation_complete"] = False
                st.session_state["generation_start"] = datetime.now()
                st.rerun()
        return

    # Check for error states and display appropriate messages
    if st.session_state.get("generation_failed"):
        n8n_ph.markdown(f"""
            <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; padding: 1.5rem; border-radius: 12px; text-align: center; margin: 1rem 0;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">❌</div>
                <h3 style="color: white; margin: 0; font-weight: 600;">Report Generation Failed</h3>
                <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;">Case ID: <strong>{case_id}</strong></p>
                <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0; font-size: 0.9rem;">The workflow encountered an error or crashed. Please try again.</p>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Retry Generation", type="primary", use_container_width=True):
                # Reset error state and restart
                st.session_state["generation_failed"] = False
                st.session_state["generation_in_progress"] = True
                st.session_state["generation_progress"] = 0
                st.session_state["generation_step"] = 0
                st.session_state["generation_complete"] = False
                st.session_state["generation_start"] = datetime.now()
                st.rerun()
        return
    
    if st.session_state.get("generation_timeout"):
        n8n_ph.markdown(f"""
            <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 1.5rem; border-radius: 12px; text-align: center; margin: 1rem 0;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">⏰</div>
                <h3 style="color: white; margin: 0; font-weight: 600;">Report Generation Timeout</h3>
                <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;">Case ID: <strong>{case_id}</strong></p>
                <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0; font-size: 0.9rem;">The workflow took longer than expected. It may still be processing in the background.</p>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Check Again", type="primary", use_container_width=True):
                # Reset timeout state and check for completion
                st.session_state["generation_timeout"] = False
                st.session_state["generation_in_progress"] = True
                st.rerun()
        return

    # Only run progress animation if not complete and we're in progress, or if it's a new case
    if (not st.session_state["generation_complete"] and st.session_state.get("generation_in_progress")) or is_new_case:
        # Demo mode: simulate progress without external dependencies
        n8n_ph.info(f"🔄 Generating report for Case ID: {case_id}")
        
        # Check for timeout (2+ hours without completion)
        elapsed_time = (datetime.now() - start_time).total_seconds()
        if elapsed_time > 7200:  # 2 hours = 7200 seconds
            st.session_state["generation_timeout"] = True
            st.session_state["generation_in_progress"] = False
            st.rerun()
        
        # Poll workflow status every 10 seconds to detect external cancellation/completion
        last_poll_time = st.session_state.get("last_poll_time", 0)
        current_time = time.time()
        if current_time - last_poll_time >= 10:  # Poll every 10 seconds
            st.session_state["last_poll_time"] = current_time
            # Check for external cancellation/completion and update state accordingly
            status = _poll_workflow_status(case_id)
            
            if status.get("cancelled") or status.get("status") == "cancelled":
                # Workflow was cancelled externally
                st.session_state["generation_cancelled"] = True
                st.session_state["generation_in_progress"] = False
                st.session_state["generation_end"] = datetime.now()
                if st.session_state.get("generation_start"):
                    st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - st.session_state["generation_start"]).total_seconds())
                st.rerun()
            
            elif status.get("completed") or status.get("status") == "completed":
                # Workflow completed - extract any completion data
                if status.get("message"):
                    try:
                        import json
                        completion_data = json.loads(status.get("message", "{}"))
                        metrics = _extract_runtime_metrics(json.dumps(completion_data))
                        if metrics:
                            st.session_state.setdefault("webhook_metrics_by_case", {})[str(case_id)] = metrics
                    except:
                        pass
                
                # Mark as complete
                st.session_state["generation_progress"] = 100
                st.session_state["generation_step"] = 4
                st.session_state["generation_complete"] = True
                st.session_state["generation_in_progress"] = False
                st.session_state["generation_end"] = datetime.now()
                if st.session_state.get("generation_start"):
                    st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - st.session_state["generation_start"]).total_seconds())
                st.rerun()
            
            elif status.get("status") == "failed" or status.get("error"):
                # Workflow failed
                st.session_state["generation_failed"] = True
                st.session_state["generation_in_progress"] = False
                st.session_state["generation_end"] = datetime.now()
                if st.session_state.get("generation_start"):
                    st.session_state["processing_seconds"] = int((st.session_state["generation_end"] - st.session_state["generation_start"]).total_seconds())
                st.rerun()
            
            # Update progress if status provides it
            elif status.get("progress") is not None:
                new_progress = min(int(status.get("progress", 0)), 95)  # Cap at 95% until completion
                if new_progress > st.session_state.get("generation_progress", 0):
                    st.session_state["generation_progress"] = new_progress
                    # Update step based on progress
                    if new_progress < 20:
                        st.session_state["generation_step"] = 0
                    elif new_progress < 40:
                        st.session_state["generation_step"] = 1
                    elif new_progress < 60:
                        st.session_state["generation_step"] = 2
                    elif new_progress < 80:
                        st.session_state["generation_step"] = 3
                    else:
                        st.session_state["generation_step"] = 4
        
        # Long-running workflow note and retry controls (only on explicit non-2xx)
        non_2xx = (st.session_state.get("last_webhook_status") is not None) and (not (200 <= int(st.session_state.get("last_webhook_status", 0)) < 300))
        if not st.session_state.get("generation_complete") and not non_2xx:
            remaining_time = max(0, 7200 - elapsed_time)
            hours_left = int(remaining_time // 3600)
            minutes_left = int((remaining_time % 3600) // 60)
            if hours_left > 0:
                time_msg = f"This workflow can take up to 2 hours. Keep this tab open; it will update automatically on completion. (Approximately {hours_left}h {minutes_left}m remaining)"
            else:
                time_msg = f"This workflow can take up to 2 hours. Keep this tab open; it will update automatically on completion. (Approximately {minutes_left}m remaining)"
            st.info(time_msg)
        if non_2xx:
            st.warning("The webhook call returned a non-success status. You can retry without reloading.")
            rcol1, rcol2, rcol3 = st.columns([0.4, 0.3, 0.3])
            with rcol1:
                if st.button("Retry now", type="primary"):
                    _reset_generation_state(case_id)
                    try:
                        url = _n8n_webhook_url()
                        status, text, final_url = _trigger_webhook(url, {"case_id": case_id}, attempts=1, timeout=10)
                        st.session_state["last_webhook_status"] = status
                        st.session_state["last_webhook_text"] = (text or "")[:300]
                        fm = st.session_state.get("__webhook_fired__", {})
                        fm[str(case_id)] = True
                        st.session_state["__webhook_fired__"] = fm
                        if final_url != url:
                            _set_n8n_webhook_url(final_url)
                        st.session_state["generation_in_progress"] = True
                    except Exception:
                        pass
                    st.rerun()
            with rcol2:
                if st.button("Cancel"):
                    _reset_generation_state(case_id)
                    st.rerun()
            with rcol3:
                new_cid = st.text_input("Change Case ID", value=case_id, key="retry_change_case")
                if st.button("Start with new ID") and new_cid:
                    _reset_generation_state(new_cid)
                    st.session_state["last_case_id"] = new_cid
                    try:
                        url = _n8n_webhook_url()
                        status, text, final_url = _trigger_webhook(url, {"case_id": new_cid}, attempts=1, timeout=10)
                        st.session_state["last_webhook_status"] = status
                        st.session_state["last_webhook_text"] = (text or "")[:300]
                        fm = st.session_state.get("__webhook_fired__", {})
                        fm[str(new_cid)] = True
                        st.session_state["__webhook_fired__"] = fm
                        if final_url != url:
                            _set_n8n_webhook_url(final_url)
                        st.session_state["generation_in_progress"] = True
                    except Exception:
                        pass
                    st.rerun()
        
        # Linear progression over 2 hours (7200 seconds)
        # Start at 5% after validation, reach 95% after 2 hours
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        # Calculate linear progress: 5% to 95% over 7200 seconds (2 hours)
        # Progress = 5 + (elapsed_time / 7200) * 90
        if elapsed_time < 7200:  # Within 2 hours
            linear_progress = min(5 + (elapsed_time / 7200) * 90, 95)
            st.session_state["generation_progress"] = int(linear_progress)
            
            # Update step status based on progress
            progress = st.session_state["generation_progress"]
            if progress < 20:
                st.session_state["generation_step"] = 0
            elif progress < 40:
                st.session_state["generation_step"] = 1
            elif progress < 60:
                st.session_state["generation_step"] = 2
            elif progress < 80:
                st.session_state["generation_step"] = 3
            else:
                st.session_state["generation_step"] = 4
        else:
            # After 2 hours, mark as complete
            st.session_state["generation_progress"] = 100
            st.session_state["generation_step"] = 4
            st.session_state["generation_complete"] = True
            st.session_state["generation_in_progress"] = False
            st.session_state["generation_end"] = datetime.now()
            st.session_state["processing_seconds"] = int(elapsed_time)
            
            # Simulate completion metrics for testing
            test_metrics = {
                "ocr_start_time": start_time.isoformat() + "Z",
                "ocr_end_time": datetime.now().isoformat() + "Z",
                "total_tokens_used": 1500,
                "total_input_tokens": 800,
                "total_output_tokens": 700,
                "docx_url": "https://example.com/test-report.docx",
                "pdf_url": "https://example.com/test-report.pdf"
            }
            st.session_state.setdefault("webhook_metrics_by_case", {})[str(case_id)] = test_metrics
            st.rerun()
        
        
        if st.session_state.get("generation_complete"):
            n8n_ph.markdown(f"""
                <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 1.5rem; border-radius: 12px; text-align: center; margin: 1rem 0;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">🎉</div>
                    <h3 style="color: white; margin: 0; font-weight: 600;">Report Generation Complete!</h3>
                    <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;">Case ID: <strong>{case_id}</strong></p>
                </div>
            """, unsafe_allow_html=True)
        else:
            n8n_ph.markdown(f"""
                <div style="background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.3); color: var(--accent); padding: 1rem; border-radius: 8px; text-align: center; margin: 1rem 0;">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">⏳</div>
                    <p style="margin: 0; font-weight: 500;">Generating report for Case ID: <strong>{case_id}</strong></p>
                    <p style="margin: 0.5rem 0 0 0; opacity: 0.8; font-size: 0.9rem;">Awaiting completion... This may take a few minutes.</p>
                </div>
            """, unsafe_allow_html=True)
    elif st.session_state["generation_complete"]:
        # Show completion status if already done
        n8n_ph.markdown(f"""
            <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 1.5rem; border-radius: 12px; text-align: center; margin: 1rem 0;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🎉</div>
                <h3 style="color: white; margin: 0; font-weight: 600;">Report Generation Complete!</h3>
                <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;">Case ID: <strong>{case_id}</strong></p>
            </div>
        """, unsafe_allow_html=True)
    
    
    # (Debug sections removed for cleaner UI)
    
    # Modern timing information section (show only when complete)
    if st.session_state.get("generation_complete"):
        end_time = st.session_state["generation_end"] or datetime.now()
        processing_seconds = st.session_state["processing_seconds"]
        
        st.markdown(f"""
            <div style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0;">
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; text-align: center;">
                    <div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: var(--accent); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;">Started</div>
                        <div style="font-weight: 500; color: var(--text);">{start_time.strftime("%b %d, %Y %I:%M %p").lstrip('0')}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: var(--accent); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;">Finished</div>
                        <div style="font-weight: 500; color: var(--text);">{end_time.strftime("%b %d, %Y %I:%M %p").lstrip('0')}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: var(--accent); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;">Elapsed Time</div>
                        <div style="font-weight: 500; color: var(--text);">{processing_seconds // 60}m {processing_seconds % 60}s</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
 
    # Only show "Report Ready" section when generation is actually complete
    if st.session_state.get("generation_complete"):
        # Modern action button section
        st.markdown("""
            <div style="text-align: center; margin: 2rem 0;">
                <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-radius: 12px; padding: 1.5rem; margin: 0 auto; max-width: 400px;">
                    <div style="color: white; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem;">🎉 Report Ready!</div>
                    <p style="color: rgba(255,255,255,0.9); margin: 0; font-size: 0.95rem;">Your comprehensive medical report has been generated and is ready for review.</p>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📊 View Results", type="primary", use_container_width=True):
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
 
 
main()