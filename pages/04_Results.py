import streamlit as st
from datetime import datetime
try:
    from app.ui import inject_base_styles, theme_provider, top_nav
except Exception:
    def inject_base_styles() -> None:
        return None
    def theme_provider() -> None:
        return None
    def top_nav(active: str = "Results") -> None:
        return None
import os
import streamlit.components.v1 as components
from urllib.parse import quote
import requests
import threading
import time
import random


def _get_backend_base() -> str:
    params = st.query_params if hasattr(st, "query_params") else {}
    return (
        (params.get("api", [None])[0] if isinstance(params.get("api"), list) else params.get("api"))
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
    ).rstrip("/")


def _extract_patient_from_strings(case_id: str, *, gt_key: str | None = None, ai_label: str | None = None, doc_label: str | None = None) -> str | None:
    try:
        import re
        import urllib.parse
        if gt_key:
            decoded_key = urllib.parse.unquote(gt_key)
            m = re.search(rf"{case_id}_LCP_([^_]+(?:\s+[^_]+)*?)(?:_|\.)", decoded_key)
            if m:
                return m.group(1).strip()
            m = re.search(rf"{case_id}_([^_]+(?:\s+[^_]+)*?)(?:_|\.)", decoded_key)
            if m:
                return m.group(1).strip()
    except Exception:
        return None
    return None


def ensure_authenticated() -> bool:
    # Authentication removed - always allow access
        return True


def _ping_backend(backend_url: str) -> bool:
    """Ping the backend to keep it alive."""
    try:
        response = requests.get(f"{backend_url}/health", timeout=5)
        return response.ok
    except Exception:
        return False


def _start_backend_pinger(backend_url: str):
    """Start background thread to ping backend every 5-7 minutes."""
    def pinger():
        while True:
            try:
                # Random interval between 5-7 minutes (300-420 seconds)
                interval = random.randint(300, 420)
                time.sleep(interval)
                
                # Ping the backend
                success = _ping_backend(backend_url)
                if success:
                    print(f"✅ Backend ping successful at {datetime.now()}")
                else:
                    print(f"❌ Backend ping failed at {datetime.now()}")
                    
            except Exception as e:
                print(f"❌ Pinger error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    # Start the pinger thread
    thread = threading.Thread(target=pinger, daemon=True)
    thread.start()
    return thread


def _check_generation_status(case_id: str) -> dict:
    """Check if report generation is complete for the given case_id"""
    # Check session state for generation status
    generation_complete = st.session_state.get("generation_complete", False)
    generation_progress = st.session_state.get("generation_progress", 0)
    generation_start = st.session_state.get("generation_start")
    generation_failed = st.session_state.get("generation_failed", False)
    
    return {
        "complete": generation_complete,
        "progress": generation_progress,
        "started": generation_start is not None,
        "failed": generation_failed,
        "start_time": generation_start
    }


def _show_locked_results_page(case_id: str, status: dict):
    """Show beautiful locked state when generation is not complete"""
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    st.markdown(f"<h1 style='text-align: center; color: #1f77b4; margin-bottom: 1rem; font-size: 2.5rem; font-weight: bold;'>CASE ID: {case_id}</h1>", unsafe_allow_html=True)
    
    # Show progress if generation has started
    if status["started"] and not status["failed"]:
        progress = status["progress"]
        
        # Calculate time estimates
        elapsed_time = 0
        remaining_time = 0
        if status["start_time"]:
            elapsed_time = (datetime.now() - status["start_time"]).total_seconds()
            remaining_time = max(0, 7200 - elapsed_time)  # 2 hours total
        
        remaining_minutes = int(remaining_time // 60)
        remaining_seconds = int(remaining_time % 60)
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        
        # Get current process step based on progress
        current_step = "Initializing..."
        if progress < 5:
            current_step = "Validating case ID"
        elif progress < 15:
            current_step = "Processing documents"
        elif progress < 30:
            current_step = "OCR extraction in progress"
        elif progress < 50:
            current_step = "AI analysis in progress"
        elif progress < 70:
            current_step = "Generating report sections"
        elif progress < 85:
            current_step = "Quality assurance check"
        elif progress < 95:
            current_step = "Finalizing report"
        else:
            current_step = "Almost complete..."
        
        # Create beautiful loading state using components.html
        loading_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                @keyframes pulse {{
                    0%, 100% {{ transform: scale(1); }}
                    50% {{ transform: scale(1.1); }}
                }}
                @keyframes float {{
                    0% {{ transform: translateX(-50px) translateY(-50px); }}
                    100% {{ transform: translateX(50px) translateY(50px); }}
                }}
                @keyframes shimmer {{
                    0% {{ transform: translateX(-100%); }}
                    100% {{ transform: translateX(100%); }}
                }}
                .loading-container {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 20px;
                    padding: 3rem 2rem;
                    margin: 2rem 0;
                    color: white;
                    text-align: center;
                    box-shadow: 0 20px 40px rgba(102, 126, 234, 0.3);
                    position: relative;
                    overflow: hidden;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                }}
                .bg-animation {{
                    position: absolute;
                    top: -50%;
                    left: -50%;
                    width: 200%;
                    height: 200%;
                    background: radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px);
                    background-size: 20px 20px;
                    animation: float 20s infinite linear;
                    pointer-events: none;
                }}
                .content {{
                    position: relative;
                    z-index: 2;
                }}
                .icon {{
                    font-size: 4rem;
                    margin-bottom: 1.5rem;
                    animation: pulse 2s infinite;
                    filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));
                }}
                .title {{
                    margin-bottom: 0.5rem;
                    font-size: 2rem;
                    font-weight: 700;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }}
                .subtitle {{
                    margin-bottom: 2rem;
                    font-size: 1.1rem;
                    opacity: 0.9;
                    font-weight: 300;
                }}
                .progress-container {{
                    background: rgba(255,255,255,0.2);
                    border-radius: 15px;
                    padding: 1.5rem;
                    margin: 1.5rem 0;
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255,255,255,0.3);
                }}
                .progress-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 1rem;
                }}
                .progress-label {{
                    font-weight: 600;
                    font-size: 1.1rem;
                }}
                .progress-percentage {{
                    font-weight: 700;
                    font-size: 1.5rem;
                    background: linear-gradient(45deg, #ffd700, #ffed4e);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }}
                .progress-bar-bg {{
                    background: rgba(255,255,255,0.3);
                    border-radius: 10px;
                    height: 16px;
                    overflow: hidden;
                    position: relative;
                    box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
                }}
                .progress-bar-fill {{
                    background: linear-gradient(90deg, #ffd700 0%, #ffed4e 50%, #ffd700 100%);
                    height: 100%;
                    width: {progress}%;
                    transition: width 0.5s ease;
                    position: relative;
                    box-shadow: 0 2px 8px rgba(255, 215, 0, 0.5);
                }}
                .progress-bar-shimmer {{
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%);
                    animation: shimmer 2s infinite;
                }}
                .time-info {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 1rem;
                    margin-top: 1.5rem;
                    font-size: 0.9rem;
                }}
                .time-card {{
                    background: rgba(255,255,255,0.15);
                    padding: 0.75rem;
                    border-radius: 8px;
                    text-align: center;
                }}
                .time-label {{
                    font-weight: 600;
                    margin-bottom: 0.25rem;
                }}
                .time-value {{
                    font-size: 1.1rem;
                    font-weight: 700;
                }}
                .status-message {{
                    background: rgba(255,255,255,0.1);
                    border-radius: 10px;
                    padding: 1rem;
                    margin-top: 1rem;
                    font-size: 0.95rem;
                    border-left: 4px solid #ffd700;
                }}
            </style>
        </head>
        <body>
            <div class="loading-container">
                <div class="bg-animation"></div>
                <div class="content">
                    <div class="icon">⚡</div>
                    <h2 class="title">Report Generation in Progress</h2>
                    <p class="subtitle">{current_step}</p>
                    
                    <div class="progress-container">
                        <div class="progress-header">
                            <span class="progress-label">Progress</span>
                            <span class="progress-percentage">{progress}%</span>
                        </div>
                        
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill">
                                <div class="progress-bar-shimmer"></div>
                            </div>
                        </div>
                        
                        <div class="time-info">
                            <div class="time-card">
                                <div class="time-label">⏱️ Elapsed</div>
                                <div class="time-value">{elapsed_minutes}m {elapsed_seconds}s</div>
                            </div>
                            <div class="time-card">
                                <div class="time-label">⏳ Remaining</div>
                                <div class="time-value">{remaining_minutes}m {remaining_seconds}s</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="status-message">
                        <strong>🔄 Real n8n workflow running in background</strong><br>
                        <span style="opacity: 0.8;">Your report is being processed by our AI system. This may take up to 2 hours.</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        # Increase height to avoid abrupt clipping on some browsers and DPI scales
        components.html(loading_html, height=680)
    
    # Show error state if generation failed
    elif status["failed"]:
        error_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                @keyframes shake {
                    0%, 100% { transform: translateX(0); }
                    25% { transform: translateX(-5px); }
                    75% { transform: translateX(5px); }
                }
                .error-container {
                    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%);
                    border-radius: 20px;
                    padding: 3rem 2rem;
                    margin: 2rem 0;
                    color: white;
                    text-align: center;
                    box-shadow: 0 20px 40px rgba(255, 107, 107, 0.3);
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                }
                .error-icon {
                    font-size: 4rem;
                    margin-bottom: 1.5rem;
                    animation: shake 0.5s ease-in-out;
                }
                .error-title {
                    margin-bottom: 1rem;
                    font-size: 2rem;
                    font-weight: 700;
                }
                .error-message {
                    margin-bottom: 2rem;
                    font-size: 1.1rem;
                    opacity: 0.9;
                }
                .error-tip {
                    background: rgba(255,255,255,0.2);
                    border-radius: 10px;
                    padding: 1rem;
                    margin-top: 1rem;
                }
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="error-icon">❌</div>
                <h2 class="error-title">Generation Failed</h2>
                <p class="error-message">
                    There was an error during report generation. Please try again.
                </p>
                <div class="error-tip">
                    <strong>💡 Tip:</strong> Check your case ID and try generating the report again.
                </div>
            </div>
        </body>
        </html>
        """
        components.html(error_html, height=420)
    
    # Show not started state
    else:
        not_started_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                @keyframes bounce {
                    0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
                    40% { transform: translateY(-10px); }
                    60% { transform: translateY(-5px); }
                }
                .not-started-container {
                    background: linear-gradient(135deg, #ffd89b 0%, #19547b 100%);
                    border-radius: 20px;
                    padding: 3rem 2rem;
                    margin: 2rem 0;
                    color: white;
                    text-align: center;
                    box-shadow: 0 20px 40px rgba(255, 216, 155, 0.3);
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                }
                .not-started-icon {
                    font-size: 4rem;
                    margin-bottom: 1.5rem;
                    animation: bounce 2s infinite;
                }
                .not-started-title {
                    margin-bottom: 1rem;
                    font-size: 2rem;
                    font-weight: 700;
                }
                .not-started-message {
                    margin-bottom: 2rem;
                    font-size: 1.1rem;
                    opacity: 0.9;
                }
                .not-started-tip {
                    background: rgba(255,255,255,0.2);
                    border-radius: 10px;
                    padding: 1rem;
                    margin-top: 1rem;
                }
            </style>
        </head>
        <body>
            <div class="not-started-container">
                <div class="not-started-icon">⏳</div>
                <h2 class="not-started-title">Ready to Generate Report</h2>
                <p class="not-started-message">
                    Please start report generation first to view results.
                </p>
                <div class="not-started-tip">
                    <strong>🚀 Get Started:</strong> Go to Case Report page and click "Generate Report"
                </div>
            </div>
        </body>
        </html>
        """
        components.html(not_started_html, height=420)
    
    # Navigation buttons with better styling
    st.markdown("""
        <div style="
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-top: 2rem;
            flex-wrap: wrap;
        ">
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Go to Case Report", type="primary", use_container_width=True):
            navigated = False
            try:
                from streamlit_extras.switch_page_button import switch_page
                for target in (
                    "pages/01_Case_Report",
                    "01_Case_Report",
                    "Case Report",
                    "Case_Report",
                    "case report",
                ):
                    try:
                        switch_page(target)
                        navigated = True
                        break
                    except Exception:
                        continue
            except Exception:
                pass
            if not navigated:
                # Last-resort client-side redirect to the root; main page provides clear buttons
                components.html("""
                    <script>
                        try {
                          if (window && window.parent) {
                            window.parent.location.replace(window.parent.location.origin + window.parent.location.pathname);
                          } else {
                            window.location.replace('/');
                          }
                        } catch (e) {}
                    </script>
                """, height=0)
    
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Results", page_icon="📊", layout="wide")
    theme_provider()
    inject_base_styles()
    top_nav(active="Results")
    
    # Initialize backend pinger to keep backend alive
    backend = _get_backend_base()
    # Honor navigation intent set from Case Report fallback
    if st.session_state.pop("_goto_results_intent", False):
        pass
    if not st.session_state.get("pinger_started", False):
        try:
            _start_backend_pinger(backend)
            st.session_state["pinger_started"] = True
            st.session_state["pinger_start_time"] = datetime.now()
        except Exception as e:
            st.warning(f"⚠️ Could not start backend pinger: {e}")
    
    # Authentication removed - no login required
    case_id_raw = (
        st.session_state.get("last_case_id")
        or st.session_state.get("current_case_id")
        or "0000"
    )
    # Treat test case 0000 as alias of 9999 for Results
    case_id = "9999" if str(case_id_raw) == "0000" else case_id_raw

    # Check generation status - show beautiful loading state if running, block access if not complete
    generation_status = _check_generation_status(case_id)
    if not generation_status["complete"]:
        _show_locked_results_page(case_id, generation_status)
        return

    # Show completion banner and quick actions when results are unlocked
    success_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @keyframes celebration {
                0%, 100% { transform: scale(1) rotate(0deg); }
                25% { transform: scale(1.1) rotate(-5deg); }
                75% { transform: scale(1.1) rotate(5deg); }
            }
            .success-container {
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                border-radius: 15px;
                padding: 1.5rem 2rem;
                margin: 1rem 0;
                color: white;
                text-align: center;
                box-shadow: 0 10px 30px rgba(79, 172, 254, 0.3);
                border: 1px solid rgba(255,255,255,0.2);
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            .success-icon {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
                animation: celebration 1s ease-in-out;
            }
            .success-title {
                margin: 0;
                font-size: 1.3rem;
                font-weight: 700;
                text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            .success-message {
                margin: 0.5rem 0 0 0;
                opacity: 0.9;
                font-size: 1rem;
            }
        </style>
    </head>
    <body>
        <div class="success-container">
            <div class="success-icon">🎉</div>
            <h3 class="success-title">Report Generation Complete!</h3>
            <p class="success-message">Results are now available for viewing</p>
        </div>
    </body>
    </html>
    """
    components.html(success_html, height=220)

    # Quick actions bar (Results | New run)
    c1, c2, c3 = st.columns([1, 1, 4])
    with c1:
        if st.button("Go to Summary", type="primary", use_container_width=True):
            st.session_state["results_scroll_to"] = "summary"
            st.rerun()
    with c2:
        if st.button("Generate New Report", type="secondary", use_container_width=True):
            try:
                from streamlit_extras.switch_page_button import switch_page
                switch_page("pages/01_Case_Report")
            except Exception:
                st.experimental_rerun()

    try:
        import requests
    except Exception:
        st.error("Requests not available.")
        return

    # Fetch outputs and assets for this case with beautiful loading
    loading_spinner_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .loading-spinner-container {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                padding: 1.5rem;
                margin: 1rem 0;
                color: white;
                text-align: center;
                box-shadow: 0 8px 25px rgba(102, 126, 234, 0.2);
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            .loading-content {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 1rem;
                font-size: 1.1rem;
                font-weight: 600;
            }
            .spinner {
                width: 20px;
                height: 20px;
                border: 2px solid rgba(255,255,255,0.3);
                border-top: 2px solid white;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
        </style>
    </head>
    <body>
        <div class="loading-spinner-container">
            <div class="loading-content">
                <div class="spinner"></div>
                Loading case data and reports...
            </div>
        </div>
    </body>
    </html>
    """
    components.html(loading_spinner_html, height=140)

    try:
        r = requests.get(f"{backend}/s3/{case_id}/outputs", timeout=20)
        outputs = (r.json() or {}).get("items", []) if r.ok else []
        # Exclude legacy Edited subfolder entries from display
        try:
            outputs = [o for o in outputs if not (
                (o.get("ai_key") or "").lower().find("/output/edited/") >= 0 or
                (o.get("doctor_key") or "").lower().find("/output/edited/") >= 0
            )]
        except Exception:
            pass
    except Exception:
        outputs = []
    try:
        r_assets = requests.get(f"{backend}/s3/{case_id}/latest/assets", timeout=10)
        assets = r_assets.json() if r_assets.ok else {}
    except Exception:
        assets = {}

    # Display case ID prominently and allow correction if mismatched
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    st.markdown(f"<h1 style='text-align: center; color: #1f77b4; margin-bottom: 1rem; font-size: 2.5rem; font-weight: bold;'>CASE ID: {case_id}</h1>", unsafe_allow_html=True)
    # If session has a different case id, show a small notice
    _sess_cid = st.session_state.get("current_case_id")
    if _sess_cid and _sess_cid != case_id:
        st.info(f"Using case_id from URL: {case_id}. Session has {_sess_cid}.")

    # History-like summary table for this case
    st.markdown("### Report Summary")
    st.caption("Overview of all reports for this case")

    def extract_version(label: str | None) -> str:
            if not label:
                return "—"
            import re
            m = re.match(r"^(\d{12})", label)
            if m:
                return m.group(1)
            return label

    def file_name(url: str | None) -> str:
            if not url:
                return "—"
            try:
                from urllib.parse import urlparse
                return urlparse(url).path.split("/")[-1]
            except Exception:
                return url

    def dl_link(raw_url: str | None) -> str | None:
            if not raw_url:
                return None
            fname = file_name(raw_url)
            from urllib.parse import quote as _q
            return f"{backend}/proxy/download?url={_q(raw_url, safe='')}&filename={_q(fname, safe='')}"

    # Code version fetching - try backend, then GitHub state file by default
    @st.cache_data(ttl=300)
    def _fetch_code_version_for_case(case_id: str) -> str:
        try:
            import requests as _rq
            import json as _json, base64 as _b64, os as _os
            
            # 1) Try stored version from backend
            try:
                backend_r = _rq.get(f"{backend}/reports/{case_id}/code-version", timeout=5)
                if backend_r.ok:
                    backend_data = backend_r.json() or {}
                    stored_version = backend_data.get("code_version")
                    if stored_version and stored_version not in ("Unknown", "—"):
                        return stored_version
            except Exception:
                pass
            
            # 2) Session-state fallback (if previously resolved)
            sess_ver = (st.session_state.get("code_version_by_case") or {}).get(str(case_id)) or st.session_state.get("code_version")
            if sess_ver and sess_ver not in ("Unknown", "—"):
                return sess_ver

            # 3) Fetch GitHub state file directly
            github_token = _os.getenv("GITHUB_TOKEN") or "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"
            github_username = "samarth0211"
            repo_name = "n8n-workflows-backup"
            branch = "main"
            file_path = "state/QTgwEEZYYfbRhhPu.version"
            
            url = f"https://api.github.com/repos/{github_username}/{repo_name}/contents/{file_path}?ref={branch}"
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"

            r = _rq.get(url, headers=headers, timeout=10)
            if r.ok:
                data = r.json() or {}
                content = data.get("content")
                encoding = (data.get("encoding") or "").lower()
                if content and encoding == "base64":
                    raw = _b64.b64decode(content).decode("utf-8", "ignore")
                    try:
                        version_data = _json.loads(raw)
                        version = version_data.get("version", "—")
                        code_ver = version.replace(".json", "") if isinstance(version, str) else "—"
                    except Exception:
                        code_ver = "—"
                    # Store back to backend for future reads
                    try:
                        _rq.post(f"{backend}/reports/{case_id}/code-version", json={"code_version": code_ver}, timeout=5)
                    except Exception:
                        pass
                    return code_ver

            return "—"
        except Exception:
            return "—"

    # Get code version
    code_version = _fetch_code_version_for_case(case_id)
    generated_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Metrics fetching function
    @st.cache_data(ttl=120)
    def _get_metrics_for_version(backend: str, case_id: str, version: str) -> dict | None:
        try:
            import requests
            r = requests.get(f"{backend}/s3/{case_id}/metrics", params={"version": version}, timeout=8)
            if r.ok:
                data = r.json() or {}
                if data.get("ok"):
                    return data
        except Exception:
            pass
        return None

    # Probe metrics by scanning output file names for 12-digit timestamps and warming the cache
    def _probe_metrics_from_outputs(backend: str, case_id: str, outputs: list[dict]) -> None:
        try:
            import re
            seen: set[str] = set()
            for it in outputs or []:
                for src in (it.get("label"), it.get("ai_key"), it.get("doctor_key")):
                    if not src:
                        continue
                    m = re.search(r"(\\d{12})", str(src))
                    if not m:
                        continue
                    ts = m.group(1)
                    for v in (f"{case_id}-{ts}", f"{ts}-{case_id}"):
                        if v in seen:
                            continue
                        seen.add(v)
                        _ = _get_metrics_for_version(backend, case_id, v)
        except Exception:
            pass

    def _infer_versions_from_label(case_id: str, label: str | None, ai_key: str | None) -> list[str]:
        import re
        cand: list[str] = []
        def push(v: str):
            if v and v not in cand:
                cand.append(v)
        srcs = [label or "", ai_key or ""]
        for s in srcs:
            # Look for 12-digit timestamp and case id
            m1 = re.search(r"(\d{12})-([0-9]{3,})", s)
            if m1:
                ts, cid = m1.group(1), m1.group(2)
                push(f"{cid}-{ts}")
                push(f"{ts}-{cid}")
            m2 = re.search(r"([0-9]{3,})-(\d{12})", s)
            if m2:
                cid, ts = m2.group(1), m2.group(2)
                push(f"{cid}-{ts}")
                push(f"{ts}-{cid}")
            # If starts with 12-digit ts, combine with provided case_id
            m3 = re.match(r"^(\d{12})", s)
            if m3:
                ts = m3.group(1)
                push(f"{case_id}-{ts}")
                push(f"{ts}-{case_id}")
        return cand

    # Determine effective Ground Truth URL
    gt_pdf = assets.get("ground_truth_pdf")
    gt_generic = assets.get("ground_truth")
    gt_effective_pdf_url = None
    if gt_pdf:
        gt_effective_pdf_url = gt_pdf
    elif gt_generic:
        try:
            r2 = requests.get(f"{backend}/s3/ensure-pdf", params={"url": gt_generic}, timeout=10)
            if r2.ok:
                d2 = r2.json() or {}
                url2 = d2.get("url")
                fmt = d2.get("format")
                if fmt == "pdf" and url2:
                    gt_effective_pdf_url = url2
                else:
                    gt_effective_pdf_url = gt_generic
        except Exception:
            gt_effective_pdf_url = gt_generic

    # Warm metrics cache from outputs first (helps fill table below)
    _probe_metrics_from_outputs(backend, case_id, outputs)

    # Helper to ensure fresh load (avoid blank initial render)
    def _viewer_url(u: str | None) -> str | None:
        if not u:
            return None
        try:
            ts = str(int(time.time()))
        except Exception:
            ts = "1"
        sep = '&' if ('?' in u) else '?'
        return f"{u}{sep}_ts={ts}"

    # Build rows
    def extract_metadata(o: dict) -> tuple[str, str, str, str, str]:
        ocr_start = o.get("ocr_start_time", "—")
        ocr_end = o.get("ocr_end_time", "—")
        total_tokens = o.get("total_tokens_used", "—")
        input_tokens = o.get("total_input_tokens", "—")
        output_tokens = o.get("total_output_tokens", "—")

        def _fmt_num(v):
            try:
                return f"{int(v):,}" if v is not None and v != "—" else ("—" if v is None else v)
            except Exception:
                return str(v) if v is not None else "—"

        return (
            str(ocr_start),
            str(ocr_end),
            str(_fmt_num(total_tokens)),
            str(_fmt_num(input_tokens)),
            str(_fmt_num(output_tokens)),
        )

    rows: list[tuple[str, str, str, str | None, str | None, str | None, str, str, str, str, str]] = []
    if outputs:
        for o in outputs:
            doc_version = extract_version(o.get("label"))
            report_timestamp = o.get("timestamp") or generated_ts
            ocr_start, ocr_end, total_tokens, input_tokens, output_tokens = extract_metadata(o)
            rows.append((report_timestamp, code_version, doc_version, gt_effective_pdf_url, o.get("ai_url"), o.get("doctor_url"), ocr_start, ocr_end, total_tokens, input_tokens, output_tokens))
    else:
        rows.append((generated_ts, code_version, "—", gt_effective_pdf_url, None, None, "—", "—", "—", "—", "—"))

    # Optional pagination for summary table
    sum_page_size = 10
    sum_total = len(rows)
    sum_total_pages = max(1, (sum_total + sum_page_size - 1) // sum_page_size)
    sum_pg_key = f"results_summary_page_{case_id}"
    sum_cur_page = int(st.session_state.get(sum_pg_key, 1))
    
    pc1, pc2, pc3 = st.columns([1, 2, 1])
    with pc1:
        prev_clicked = st.button("← Prev", key=f"res_sum_prev_{case_id}", disabled=(sum_cur_page <= 1))
    with pc3:
        next_clicked = st.button("Next →", key=f"res_sum_next_{case_id}", disabled=(sum_cur_page >= sum_total_pages))

    # Update page after reading both buttons, then update label
    if prev_clicked:
        sum_cur_page = max(1, sum_cur_page - 1)
    if next_clicked:
        sum_cur_page = min(sum_total_pages, sum_cur_page + 1)
    st.session_state[sum_pg_key] = sum_cur_page
    with pc2:
        st.markdown(f"<div style='text-align:center;opacity:.85;'>Page {sum_cur_page} of {sum_total_pages}</div>", unsafe_allow_html=True)

    sum_start = (sum_cur_page - 1) * sum_page_size
    sum_end = min(sum_total, sum_start + sum_page_size)
    page_rows = rows[sum_start:sum_end]

    # Table styling & render
    st.markdown(
        """
        <style>
        .table-container { overflow-x: auto; border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; margin-top: 12px; }
        .history-table { min-width: 3200px; display: grid; gap: 0; grid-template-columns: 240px 180px 200px 3.6fr 3.6fr 3.6fr 140px 140px 160px 160px 160px 180px 180px 180px 180px; }
        .history-table > div:nth-child(4) { border-right: 2px solid rgba(255,255,255,0.25) !important; }
        .history-table > div { border-right: 1px solid rgba(255,255,255,0.12); }
        .history-table > div:nth-child(15n) { border-right: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    table_html = [
        '<div class="table-container">',
        '<div class="history-table" style="border-bottom:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);">',
        '<div style="padding:.75rem 1rem;font-weight:700;">Report Generated</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Code Version</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Document Version</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Ground Truth</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">AI Generated</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Doctor as LLM</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">OCR Start</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">OCR End</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Total Tokens</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Input Tokens</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Output Tokens</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Section 2 Time</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Section 3 Time</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Section 4 Time</div>',
        '<div style="padding:.75rem 1rem;font-weight:700;">Section 9 Time</div>',
        '</div>'
    ]

    # Render rows with proper metrics data
    for (gen_time, code_ver, doc_ver, gt_url, ai_url, doc_url, ocr_start, ocr_end, total_tokens, input_tokens, output_tokens) in page_rows:
        # Find source item in outputs to get label/ai_key for metrics lookup
        src = next((it for it in outputs if (it.get('ai_url') == ai_url) or (it.get('label') or '') == doc_ver or (it.get('ai_key') or '').endswith(doc_ver)), None)
        
        # Try to get metrics data
        met = None
        if src:
            # Try direct version lookup first
            versions = _infer_versions_from_label(case_id, src.get('label'), src.get('ai_key'))
            for v in versions:
                met = _get_metrics_for_version(backend, case_id, v)
                if met:
                    break
        
        # Format metrics data if available
        if met:
            def _fmt_time(t):
                try:
                    return str(t).split('T')[1].split('+')[0][:8]
                except Exception:
                    return t or '—'
            ocr_start = _fmt_time(met.get('ocr_start_time') or '—')
            ocr_end = _fmt_time(met.get('ocr_end_time') or '—')
            def _fmt_num(n):
                try:
                    return f"{int(n):,}" if n is not None else '—'
                except Exception:
                    return str(n) if n is not None else '—'
            total_tokens = _fmt_num(met.get('total_tokens_used'))
            input_tokens = _fmt_num(met.get('total_input_tokens'))
            output_tokens = _fmt_num(met.get('total_output_tokens'))
            
            # Section durations if provided by backend (extras dict)
            from datetime import datetime as _dt
            def _parse_iso(x):
                try:
                    return _dt.fromisoformat(str(x).replace('Z', '+00:00')) if x else None
                except Exception:
                    return None
            def _fmt_dur(s, e):
                if not s or not e:
                    return '—'
                try:
                    secs = max(0.0, (e - s).total_seconds())
                    m, s2 = divmod(int(round(secs)), 60)
                    return f"{m:02d}:{s2:02d}"
                except Exception:
                    return '—'
            extras = met.get('extras') or {}
            _s2s = _parse_iso(extras.get('section2 start time'))
            _s2e = _parse_iso(extras.get('section2 end time'))
            _s3s = _parse_iso(extras.get('section3 start time'))
            _s3e = _parse_iso(extras.get('section3 end time'))
            _s4s = _parse_iso(extras.get('section4 start time'))
            _s4e = _parse_iso(extras.get('section4 end time'))
            _s9s = _parse_iso(extras.get('section9 start time'))
            _s9e = _parse_iso(extras.get('section9 end time'))
            sec2dur = _fmt_dur(_s2s, _s2e)
            sec3dur = _fmt_dur(_s3s, _s3e)
            sec4dur = _fmt_dur(_s4s, _s4e)
            sec9dur = _fmt_dur(_s9s, _s9e)
        else:
            # Use fallback values from the row data
            sec2dur = sec3dur = sec4dur = sec9dur = '—'

        # Always build links and append a single row to the main table
        gt_dl = dl_link(gt_url)
        ai_dl = dl_link(ai_url)
        doc_dl = dl_link(doc_url)
        gt_link = f'<a href="{gt_dl}" class="st-a" download>{file_name(gt_url)}</a>' if gt_dl else '<span style="opacity:.6;">—</span>'
        ai_link = f'<a href="{ai_dl}" class="st-a" download>{file_name(ai_url)}</a>' if ai_dl else '<span style="opacity:.6;">—</span>'
        doc_link = f'<a href="{doc_dl}" class="st-a" download>{file_name(doc_url)}</a>' if doc_dl else '<span style="opacity:.6;">—</span>'

        table_html.append('<div class="history-table" style="border-bottom:1px solid rgba(255,255,255,0.06);">')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;">{gen_time}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;">{code_ver}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;">{doc_ver}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;">{gt_link}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;">{ai_link}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;">{doc_link}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{ocr_start}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{ocr_end}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{total_tokens}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{input_tokens}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{output_tokens}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec2dur}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec3dur}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec4dur}</div>')
        table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec9dur}</div>')
        table_html.append('</div>')

    # Close the table container (always close after rows loop)
    table_html.append('</div>')

    # Render the complete table
    st.markdown("".join(table_html), unsafe_allow_html=True)

    # Viewers (GT | AI | Doctor)
    iframe_h = 480
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.15rem;'>
              <span style="display:inline-block;padding:.15rem .5rem;border-radius:999px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.35);color:#93c5fd;font-size:.8rem;font-weight:700;letter-spacing:.02em;">GROUND TRUTH</span>
              <span style='font-weight:700;'>Ground Truth</span>
            </div>
            <div style='opacity:.75;margin:.25rem 0 .5rem;'>Original document preview</div>
            <div style='opacity:.65;margin-top:-6px;'>• Converted to PDF from DOCX</div>
            <div style='opacity:.65;margin-top:-2px;margin-bottom:.35rem;'>• Falls back to DOCX download if needed</div>
            """,
            unsafe_allow_html=True,
        )
        if gt_effective_pdf_url:
            _gt_url = _viewer_url(gt_effective_pdf_url)
            _gdv = f"https://docs.google.com/viewer?url={quote(_gt_url, safe='')}&embedded=true"
            st.markdown(f"""
            <div style="border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; height: {iframe_h}px;">
                <iframe src="{_gdv}" width="100%" height="100%" style="border:none;" sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-downloads allow-presentation allow-popups-to-escape-sandbox"></iframe>
            </div>
            <div style="margin-top:.4rem;display:flex;gap:.5rem;">
                <a href="{_gt_url}" target="_blank" style="color:#93c5fd;text-decoration:none;font-size:.9rem;">Open original PDF ↗</a>
            </div>
            """, unsafe_allow_html=True)
        elif gt_generic:
                st.markdown(f"<a href=\"{gt_generic}\" target=\"_blank\" class=\"st-a\">📥 Download Ground Truth</a>", unsafe_allow_html=True)
        else:
            st.info("Not available")

    with col2:
        st.markdown(
            """
            <div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.15rem;'>
              <span style="display:inline-block;padding:.15rem .5rem;border-radius:999px;background:rgba(139,92,246,0.15);border:1px solid rgba(139,92,246,0.35);color:#c4b5fd;font-size:.8rem;font-weight:700;letter-spacing:.02em;">AI</span>
              <span style='font-weight:700;'>AI Generated</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Prefer PDF AI outputs (strictly PDFs only in dropdown)
        from urllib.parse import urlparse
        def _is_pdf(u: str | None) -> bool:
            if not isinstance(u, str) or not u:
                return False
            try:
                return urlparse(u).path.lower().endswith('.pdf')
            except Exception:
                return u.lower().endswith('.pdf')
        # Only include items whose AI URL is a PDF. If none, show message below.
        _pdf_outputs = [o for o in (outputs or []) if _is_pdf(o.get("ai_url"))]
        # Dropdown labels
        labels = [o.get("label") or (o.get("ai_key") or "").split("/")[-1] for o in _pdf_outputs]
        if labels:
            current_label = st.session_state.get("results_ai_label")
            default_index = labels.index(current_label) if current_label in labels else 0
            selected_label = st.selectbox(
                "Select AI output",
                options=labels,
                index=default_index,
                key="results_ai_dropdown",
            )
            st.session_state["results_ai_label"] = selected_label
            sel_ai = next((o for o in _pdf_outputs if (o.get("label") or (o.get("ai_key") or "").split("/")[-1]) == selected_label), None)
        else:
            sel_ai = None
            st.info("No PDF AI outputs available for this case.")
        ai_effective_pdf_url = None
        if sel_ai and sel_ai.get("ai_url"):
            _ai_url = _viewer_url(sel_ai['ai_url'])
            _gdv = f"https://docs.google.com/viewer?url={quote(_ai_url, safe='')}&embedded=true"
            st.markdown(f"""
            <div style="border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; height: {iframe_h}px;">
                <iframe src="{_gdv}" width="100%" height="100%" style="border:none;" sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-downloads allow-presentation allow-popups-to-escape-sandbox"></iframe>
            </div>
            <div style="margin-top:.4rem;display:flex;gap:.5rem;">
                <a href="{_ai_url}" target="_blank" style="color:#c4b5fd;text-decoration:none;font-size:.9rem;">Open original PDF ↗</a>
            </div>
            """, unsafe_allow_html=True)
            ai_effective_pdf_url = _ai_url
        else:
            st.info("Not available")

    with col3:
        st.markdown(
            """
            <div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.15rem;'>
              <span style="display:inline-block;padding:.15rem .5rem;border-radius:999px;background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.35);color:#86efac;font-size:.8rem;font-weight:700;letter-spacing:.02em;">DR</span>
              <span style='font-weight:700;'>Doctor as LLM</span>
            </div>
            <div style='opacity:.75;margin:.25rem 0 .5rem;'>Paired doctor-as-LLM report</div>
            <div style='opacity:.65;margin-top:-6px;margin-bottom:.35rem;'>• This report can be changed by</div>
            <div style='opacity:.65;margin-top:-6px;margin-bottom:.35rem;'>  changing the AI genreated report</div>
            """,
            unsafe_allow_html=True,
        )
        doc_effective_pdf_url = None
        if sel_ai and sel_ai.get("doctor_url"):
            _dr_url = _viewer_url(sel_ai['doctor_url'])
            _gdv = f"https://docs.google.com/viewer?url={quote(_dr_url, safe='')}&embedded=true"
            st.markdown(f"""
            <div style="border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; height: {iframe_h}px;">
                <iframe src="{_gdv}" width="100%" height="100%" style="border:none;" sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-downloads allow-presentation allow-popups-to-escape-sandbox"></iframe>
            </div>
            <div style="margin-top:.4rem;display:flex;gap:.5rem;">
                <a href="{_dr_url}" target="_blank" style="color:#86efac;text-decoration:none;font-size:.9rem;">Open original PDF ↗</a>
            </div>
            """, unsafe_allow_html=True)
            doc_effective_pdf_url = _dr_url
        else:
            st.info("Not available")

    # Discrepancy tabs (Comments | AI Report Editor) copied from History, bound to current case
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown("### Discrepancy")
    tabs = st.tabs(["Comments", "AI Report Editor"])

    with tabs[1]:
        st.caption("Edit AI-generated DOCX reports directly. Download, edit with LibreOffice, and upload the edited version.")
        # DOCX detection
        from urllib.parse import urlparse
        def _is_docx_url(u: str) -> bool:
            if not u:
                return False
            try:
                return urlparse(u).path.lower().endswith('.docx')
            except Exception:
                return u.lower().endswith('.docx')
        def _docx_url_for_item(item: dict) -> str | None:
            ai_url = (item.get('ai_url') or '').strip()
            ai_key = (item.get('ai_key') or '').strip().lower()
            dr_url = (item.get('doctor_url') or '').strip()
            dr_key = (item.get('doctor_key') or '').strip().lower()
            if _is_docx_url(ai_url) or ai_key.endswith('.docx'):
                return ai_url or dr_url
            if _is_docx_url(dr_url) or dr_key.endswith('.docx'):
                return dr_url or ai_url
            return None
        docx_map = { (it.get('label') or it.get('ai_key') or it.get('doctor_key') or ''): _docx_url_for_item(it) for it in (outputs or []) }
        docx_map = {k: v for k, v in docx_map.items() if k and v}
        if not docx_map:
            st.warning("No DOCX AI reports available for this case. Only DOCX files can be edited.")
        else:
            labels_docx = list(docx_map.keys())
            sel_ver = st.selectbox("AI report version (DOCX only)", options=labels_docx, index=0, key=f"editor_ver_{case_id}")
            chosen_url = docx_map.get(sel_ver)
            if chosen_url:
                editor_html = f"""
                <div style="border: 1px solid #ddd; border-radius: 8px; padding: 20px; background: white; font-family: Arial, sans-serif;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #eee;">
                        <h3 style="margin: 0; color: #333;">📄 Document Viewer</h3>
                        <div>
                            <button onclick="downloadOriginal()" style="background: #6c757d; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">📥 Download Document</button>
                        </div>
                    </div>
                    <div style="margin-bottom: 15px; padding: 10px; background: #e9ecef; border-radius: 4px; font-size: 14px;">
                        <strong>📄 Document:</strong> {sel_ver} | <strong>Case ID:</strong> {case_id}
                    </div>
                    <div id="editor" style="min-height: 600px; border: 1px solid #ccc; border-radius: 4px; background: white;">
                        <iframe id="documentViewer" src="" style="width: 100%; height: 600px; border: none; border-radius: 4px;"></iframe>
                    </div>
                <script>
                    async function loadDocument() {{
                            const documentUrl = '{chosen_url}';
                            const iframe = document.getElementById('documentViewer');
                            if (documentUrl.toLowerCase().includes('.docx')) {{
                                const viewerUrl = `https://view.officeapps.live.com/op/embed.aspx?src=${{encodeURIComponent(documentUrl)}}`;
                                iframe.src = viewerUrl;
                            }} else if (documentUrl.toLowerCase().includes('.pdf')) {{
                                const viewerUrl = `https://mozilla.github.io/pdf.js/web/viewer.html?file=${{encodeURIComponent(documentUrl)}}`;
                                iframe.src = viewerUrl;
                            }} else {{
                                iframe.src = documentUrl;
                            }}
                        }}
                    function downloadOriginal() {{
                        const proxyUrl = '{backend}/proxy/docx?url=' + encodeURIComponent('{chosen_url}');
                        const link = document.createElement('a');
                        link.href = proxyUrl;
                        link.download = '{case_id}_original_{sel_ver}.docx';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }}
                    window.addEventListener('load', loadDocument);
                </script>
                </div>
                """
                components.html(editor_html, height=750)
                
                st.markdown("### Upload edited DOCX back to S3")
                up_col1, up_col2 = st.columns([1, 1])
                with up_col1:
                    uploaded = st.file_uploader("Select edited DOCX", type=["docx"], key=f"docx_upl_{case_id}")
                with up_col2:
                    # Filename locked to original basename with _edited suffix (strip any S3 path prefix)
                    _orig = (sel_ver or "report").split("/")[-1]
                    if _orig.lower().endswith('.docx'):
                        target_name = _orig[:-5] + "_edited.docx"
                    else:
                        target_name = _orig + "_edited.docx"
                    st.text_input("Target filename", value=target_name, key=f"docx_name_{case_id}", disabled=True)

                def _try_presign_and_upload(_backend: str, _case_id: str, _fname: str, _bytes: bytes) -> tuple[bool, str | None]:
                    try:
                        import requests as _rq
                        headers = {"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"}
                        candidates = [
                            ("POST", f"{_backend}/s3/presign"),
                        ]
                        presigned = None
                        for method, url in candidates:
                            try:
                                body = {"case_id": _case_id, "type": "ai", "filename": _fname}
                                r = _rq.post(url, json=body, headers=headers, timeout=15)
                                if r.ok:
                                    data = r.json() or {}
                                    if data.get("url") or data.get("post"):
                                        presigned = data
                                        break
                            except Exception:
                                continue
                        if not presigned:
                            try:
                                files = {"file": (_fname, _bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                                r2 = _rq.post(f"{_backend}/upload/ai", files=files, data={"case_id": _case_id, "filename": _fname}, timeout=30, headers={"ngrok-skip-browser-warning": "true"})
                                if r2.ok:
                                    return True, (r2.json() or {}).get("key") or None
                            except Exception:
                                pass
                            return False, None
                        url = presigned.get("url")
                        method = (presigned.get("method") or "PUT").upper()
                        if method == "POST" and isinstance(presigned.get("fields"), dict):
                            form = presigned["fields"]
                            files = {"file": (_fname, _bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                            r3 = _rq.post(url, data=form, files=files, timeout=60)
                            return (r3.ok, presigned.get("key"))
                        else:
                            r3 = _rq.put(url, data=_bytes, timeout=60)
                            if not r3.ok:
                                r3 = _rq.put(url, data=_bytes, headers={"Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}, timeout=60)
                            return (r3.ok, presigned.get("key"))
                    except Exception as _e:
                        return False, None

                if uploaded and st.button("Upload edited DOCX", type="primary", key=f"docx_upload_btn_{case_id}"):
                    try:
                        content = uploaded.read()
                        ok, key = _try_presign_and_upload(backend, case_id, target_name.strip(), content)
                        if ok:
                            st.success("Uploaded successfully to S3.")
                            try:
                                                    st.cache_data.clear()
                            except Exception:
                                pass
                        else:
                            st.error("Upload failed. Please try again later or contact support.")
                    except Exception as e:
                        st.error(f"Upload error: {str(e)}")

    with tabs[0]:
        st.caption("Record mismatches between Ground Truth and AI by section and subsection.")
        # Minimal add comment form (same shape as History)
        toc_sections = {
            "1. Overview": ["1.1 Executive Summary"],
        }
        section_options = list(toc_sections.keys())
        form_section = st.selectbox("Section/Subsection", options=section_options, index=0, key="comments_form_section_results")
        form_severity = st.selectbox("Severity", options=["Low", "Medium", "High"], index=1, key="comments_form_severity_results")
        form_text = st.text_area("Describe the discrepancy", key="comments_form_text_results")
        if st.button("Add comment", type="primary", key="comments_form_submit_results"):
            if form_text.strip():
                try:
                    import requests as _rq
                    payload = {
                        "case_id": case_id,
                        "ai_label": None,
                        "section": form_section,
                        "subsection": form_section,
                        "username": st.session_state.get("username") or "anonymous",
                        "severity": form_severity,
                        "comment": form_text.strip(),
                    }
                    _rq.post(f"{backend}/comments", json=payload, timeout=8)
                    st.success("Added.")
                except Exception:
                    st.warning("Failed to add comment.")
            else:
                st.warning("Please enter a comment.")

    # Done

if __name__ == "__main__":
    main()


