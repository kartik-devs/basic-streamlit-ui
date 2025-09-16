import streamlit as st
from datetime import datetime
from app.ui import inject_base_styles, theme_provider, top_nav
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
    """Show locked state when generation is not complete"""
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    st.markdown(f"<h1 style='text-align: center; color: #1f77b4; margin-bottom: 1rem; font-size: 2.5rem; font-weight: bold;'>CASE ID: {case_id}</h1>", unsafe_allow_html=True)
    
    # Show lock icon and message
    st.markdown("""
        <div style="text-align: center; padding: 3rem 2rem; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 16px; margin: 2rem 0;">
            <div style="font-size: 4rem; margin-bottom: 1rem;">🔒</div>
            <h2 style="color: #495057; margin-bottom: 1rem;">Results Not Ready</h2>
            <p style="color: #6c757d; font-size: 1.1rem; margin-bottom: 2rem;">
                Your report is still being generated. Results will be available once the process is 100% complete.
            </p>
    """, unsafe_allow_html=True)
    
    # Show progress if generation has started
    if status["started"] and not status["failed"]:
        progress = status["progress"]
        st.markdown(f"""
            <div style="background: white; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <span style="font-weight: 600; color: #495057;">Generation Progress</span>
                    <span style="font-weight: 700; color: #1f77b4; font-size: 1.2rem;">{progress}%</span>
                        </div>
                <div style="background: #e9ecef; border-radius: 8px; height: 12px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, #1f77b4 0%, #17a2b8 100%); height: 100%; width: {progress}%; transition: width 0.3s ease;"></div>
                            </div>
                <div style="text-align: center; margin-top: 1rem; color: #6c757d; font-size: 0.9rem;">
                    {progress}% Complete
                        </div>
                            </div>
        """, unsafe_allow_html=True)
    
    # Show error state if generation failed
    elif status["failed"]:
        st.markdown("""
            <div style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); color: white; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; text-align: center;">
                <div style="font-size: 2rem; margin-bottom: 1rem;">❌</div>
                <h3 style="margin-bottom: 1rem;">Generation Failed</h3>
                <p style="margin-bottom: 1.5rem; opacity: 0.9;">
                    There was an error during report generation. Please try again.
                </p>
                </div>
        """, unsafe_allow_html=True)
    
    # Show not started state
    else:
        st.markdown("""
            <div style="background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%); color: #212529; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; text-align: center;">
                <div style="font-size: 2rem; margin-bottom: 1rem;">⏳</div>
                <h3 style="margin-bottom: 1rem;">Generation Not Started</h3>
                <p style="margin-bottom: 1.5rem; opacity: 0.8;">
                    Please start report generation first to view results.
                </p>
                </div>
        """, unsafe_allow_html=True)
    
    # Navigation buttons
    st.markdown("""
        </div>
    """, unsafe_allow_html=True)
    
    def _robust_switch_to_case_report():
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
                    return True
                except Exception:
                    continue
        except Exception:
            pass
        # Fallback: client-side redirect to root; main page should provide clear nav
        components.html(
            """
            <script>
              try {
                if (window && window.parent) {
                  window.parent.location.replace(window.parent.location.origin + window.parent.location.pathname);
                } else {
                  window.location.replace('/');
                }
              } catch (e) {}
            </script>
            """,
            height=0,
        )
        return False

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Go to Generating Report", type="primary", use_container_width=True):
            # Generating happens on Case Report; route there robustly
            _robust_switch_to_case_report()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📋 Go to Case Report", type="secondary", use_container_width=True):
            _robust_switch_to_case_report()


def main() -> None:
    st.set_page_config(page_title="Results", page_icon="📊", layout="wide")
    theme_provider()
    inject_base_styles()
    top_nav(active="Results")
    
    # Initialize backend pinger to keep backend alive
    backend = _get_backend_base()
    if not st.session_state.get("pinger_started", False):
        try:
            _start_backend_pinger(backend)
            st.session_state["pinger_started"] = True
            st.session_state["pinger_start_time"] = datetime.now()
        except Exception as e:
            st.warning(f"⚠️ Could not start backend pinger: {e}")
    
    # Authentication removed - no login required
    case_id = (
        st.session_state.get("last_case_id")
        or st.session_state.get("current_case_id")
        or "0000"
    )
    if case_id == "0000":
        st.info("No active case. Go to Case Report and start a run.")
        return

    # Check generation status - show progress if running, block access if not complete
    generation_status = _check_generation_status(case_id)
    if not generation_status["complete"]:
        # Check if generation is in progress
        if st.session_state.get("generation_in_progress", False):
            progress = generation_status["progress"]
            st.info(f"🔄 Report is currently being generated... Progress: {progress}%")
            st.progress(progress / 100)
            
            # Show estimated time remaining
            if generation_status["start_time"]:
                elapsed_time = (datetime.now() - generation_status["start_time"]).total_seconds()
                remaining_time = max(0, 7200 - elapsed_time)  # 2 hours total
                remaining_minutes = int(remaining_time // 60)
                remaining_seconds = int(remaining_time % 60)
                st.info(f"⏱️ Estimated time remaining: {remaining_minutes}m {remaining_seconds}s")
            
            st.info("Please wait for the report to complete before viewing results.")
        else:
            st.info("ℹ️ No report generation in progress. Please go to Case Report to start generating a report.")
        return

    # Show success message when results are unlocked
    st.success("🎉 Report generation complete! Results are now available.")

    try:
        import requests
    except Exception:
        st.error("Requests not available.")
        return

    # Fetch outputs and assets for this case
    with st.spinner("Loading case data…"):
        try:
            r = requests.get(f"{backend}/s3/{case_id}/outputs", timeout=20)
            outputs = (r.json() or {}).get("items", []) if r.ok else []
            # Also fetch latest assets to get Ground Truth last modified
            r_assets = requests.get(f"{backend}/s3/{case_id}/latest/assets", timeout=10)
            assets = r_assets.json() if r_assets.ok else {}
        except Exception:
            outputs = []
            assets = {}
        # Exclude legacy Edited subfolder entries from display
        try:
            outputs = [o for o in outputs if not (
                (o.get("ai_key") or "").lower().find("/output/edited/") >= 0 or
                (o.get("doctor_key") or "").lower().find("/output/edited/") >= 0
            )]
        except Exception:
            pass
        
        # Sort outputs by S3 LastModified when available; fallback to embedded timestamp
        def _ts_key(item: dict):
            from datetime import datetime as _dt
            iso = item.get('sort_last_modified') or item.get('ai_last_modified') or item.get('doctor_last_modified')
            if isinstance(iso, str):
                try:
                    return _dt.fromisoformat(iso)
                except Exception:
                    pass
            import re
            try:
                src = (item.get('ai_key') or item.get('label') or '')
                m = re.search(r"(\d{12})", str(src))
                return m.group(1) if m else ''
            except Exception:
                return ''
        try:
            outputs.sort(key=_ts_key, reverse=True)  # True = latest first (reverse chronological)
        except Exception:
            pass

    # Optionally show only canonical workflow reports which can have metrics JSON
    st.markdown("<div style='height:.25rem'></div>", unsafe_allow_html=True)
    only_canonical = st.checkbox(
        "Show only canonical workflow reports (with metrics)",
        value=True,
        key=f"hist_only_canon_{case_id}",
    )
    if outputs and only_canonical:
        try:
            import re as _re
            def _base_name(it: dict) -> str:
                return (it.get("label") or (it.get("ai_key") or "").split("/")[-1] or "").strip()
            canon_re = _re.compile(rf"^(\d{{12}})-{case_id}-CompleteAIGeneratedReport\.(pdf|docx)$", _re.IGNORECASE)
            filtered = [o for o in outputs if canon_re.match(_base_name(o) or "")]
            if filtered:
                outputs = filtered
            else:
                st.info("No canonical reports found. Showing all outputs.")
        except Exception:
            pass

    # Display case ID prominently
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    st.markdown(f"<h1 style='text-align: center; color: #1f77b4; margin-bottom: 1rem; font-size: 2.5rem; font-weight: bold;'>CASE ID: {case_id}</h1>", unsafe_allow_html=True)

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

    def extract_date_from_url(url: str | None) -> str:
            if not url:
                return "—"
            try:
                import re
                from urllib.parse import urlparse
                
                # Look for 12-digit timestamp pattern (YYYYMMDDHHMM) in URL
                match = re.search(r"(\d{12})", str(url))
                if match:
                    timestamp = match.group(1)
                    # Convert YYYYMMDDHHMM to readable format
                    year = timestamp[:4]
                    month = timestamp[4:6]
                    day = timestamp[6:8]
                    hour = timestamp[8:10]
                    minute = timestamp[10:12]
                    return f"{year}-{month}-{day} {hour}:{minute}"
                
                # If no timestamp in URL, try to extract from filename
                parsed_url = urlparse(url)
                filename = parsed_url.path.split("/")[-1]
                
                # Look for timestamp in filename
                filename_match = re.search(r"(\d{12})", filename)
                if filename_match:
                    timestamp = filename_match.group(1)
                    year = timestamp[:4]
                    month = timestamp[4:6]
                    day = timestamp[6:8]
                    hour = timestamp[8:10]
                    minute = timestamp[10:12]
                    return f"{year}-{month}-{day} {hour}:{minute}"
                
                # Look for other date patterns in filename (YYYY-MM-DD, YYYYMMDD, etc.)
                date_patterns = [
                    r"(\d{4}-\d{2}-\d{2})",  # YYYY-MM-DD
                    r"(\d{8})",              # YYYYMMDD
                    r"(\d{4}_\d{2}_\d{2})",  # YYYY_MM_DD
                ]
                
                for pattern in date_patterns:
                    date_match = re.search(pattern, filename)
                    if date_match:
                        date_str = date_match.group(1)
                        # Try to parse and format the date
                        try:
                            if '-' in date_str:
                                year, month, day = date_str.split('-')
                            elif '_' in date_str:
                                year, month, day = date_str.split('_')
                            else:  # YYYYMMDD
                                year = date_str[:4]
                                month = date_str[4:6]
                                day = date_str[6:8]
                            
                            return f"{year}-{month}-{day}"
                        except:
                            continue
                
                # For Ground Truth files (reference files), show a static label
                # Ground Truth files are typically in GroundTruth/ or Ground Truth/ folders
                # and don't contain timestamps, so they should show as "Reference"
                if ("ground" in filename.lower() or 
                    "reference" in filename.lower() or
                    "LCP_" in filename or  # Pattern like 4244_LCP_Natasha...
                    filename.endswith(('.pdf', '.docx')) and not re.search(r'\d{12}', filename)):
                    return "Reference"
                
                # Fallback to filename if no date found
                return filename
            except Exception:
                return url

    def calculate_ocr_duration(ocr_start: str, ocr_end: str) -> str:
            if not ocr_start or not ocr_end or ocr_start == "—" or ocr_end == "—":
                return "—"
            try:
                from datetime import datetime, time
                
                # Handle different time formats
                def parse_time(time_str: str) -> datetime:
                    time_str = str(time_str).strip()
                    
                    # If it's a full ISO datetime string
                    if 'T' in time_str:
                        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    
                    # If it's just a time string (HH:MM:SS)
                    elif ':' in time_str and len(time_str.split(':')) >= 2:
                        time_parts = time_str.split(':')
                        if len(time_parts) >= 2:
                            hours = int(time_parts[0])
                            minutes = int(time_parts[1])
                            seconds = int(time_parts[2]) if len(time_parts) > 2 else 0
                            # Create a datetime for today with the given time
                            today = datetime.now().replace(hour=hours, minute=minutes, second=seconds, microsecond=0)
                            return today
                    
                    # If it's a timestamp (seconds since epoch)
                    elif time_str.isdigit():
                        return datetime.fromtimestamp(int(time_str))
                    
                    raise ValueError(f"Unrecognized time format: {time_str}")
                
                start_dt = parse_time(ocr_start)
                end_dt = parse_time(ocr_end)
                
                # Calculate duration
                duration = end_dt - start_dt
                total_seconds = int(duration.total_seconds())
                
                # Handle negative durations (might happen with time-only strings)
                if total_seconds < 0:
                    total_seconds = abs(total_seconds)
                
                minutes, seconds = divmod(total_seconds, 60)
                return f"{minutes:02d}:{seconds:02d}"
            except Exception as e:
                # Debug: print the error to help troubleshoot
                print(f"OCR duration calculation error: {e}, start: {ocr_start}, end: {ocr_end}")
                return "—"

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

    # Comments API helper (from History page)
    @st.cache_data(show_spinner=False, ttl=60)
    def _get_case_comments(backend: str, case_id: str, ai_label: str = None) -> list[dict]:
        try:
            import requests as _rq
            params = {"ai_label": ai_label} if ai_label else None
            r = _rq.get(f"{backend}/comments/{case_id}", params=params, timeout=8)
            if r.ok:
                return r.json() or []
        except Exception:
            pass
        return []

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

    rows: list[tuple[str, str, str | None, str | None, str | None, str, str, str, str, str]] = []
    if outputs:
            for o in outputs:
                report_timestamp = o.get("timestamp") or generated_ts
                ocr_start, ocr_end, total_tokens, input_tokens, output_tokens = extract_metadata(o)
                rows.append((report_timestamp, code_version, gt_effective_pdf_url, o.get("ai_url"), o.get("doctor_url"), ocr_start, ocr_end, total_tokens, input_tokens, output_tokens))
    else:
        rows.append((generated_ts, code_version, gt_effective_pdf_url, None, None, "—", "—", "—", "—", "—"))

    # Optional pagination for summary table
    sum_page_size = 10
    sum_total = len(rows)
    sum_total_pages = max(1, (sum_total + sum_page_size - 1) // sum_page_size)
    sum_pg_key = f"results_summary_page_{case_id}"
    sum_cur_page = int(st.session_state.get(sum_pg_key, 1))

    pc1, pc2, pc3 = st.columns([1, 2, 1])
    with pc1:
        if st.button("← Prev", key=f"res_sum_prev_{case_id}", disabled=(sum_cur_page <= 1)):
        sum_cur_page = max(1, sum_cur_page - 1)
    with pc2:
        st.markdown(f"<div style='text-align:center;opacity:.85;'>Page {sum_cur_page} of {sum_total_pages}</div>", unsafe_allow_html=True)
    with pc3:
        if st.button("Next →", key=f"res_sum_next_{case_id}", disabled=(sum_cur_page >= sum_total_pages)):
            sum_cur_page = min(sum_total_pages, sum_cur_page + 1)

    st.session_state[sum_pg_key] = sum_cur_page
    sum_start = (sum_cur_page - 1) * sum_page_size
    sum_end = min(sum_total, sum_start + sum_page_size)
    page_rows = rows[sum_start:sum_end]

    # Table styling & render
        st.markdown(
            """
            <style>
            .table-container { overflow-x: auto; border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; margin-top: 12px; }
            .history-table { min-width: 2900px; display: grid; gap: 0; grid-template-columns: 240px 180px 3.6fr 3.6fr 3.6fr 100px 160px 160px 160px 180px 180px 180px 180px; }
            .history-table > div:nth-child(3) { border-right: 2px solid rgba(255,255,255,0.25) !important; }
            .history-table > div { border-right: 1px solid rgba(255,255,255,0.12); }
            .history-table > div:nth-child(13n) { border-right: none; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        table_html = [
            '<div class="table-container">',
            '<div class="history-table" style="border-bottom:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);">',
            '<div style="padding:.75rem 1rem;font-weight:700;">Report Generated</div>',
            '<div style="padding:.75rem 1rem;font-weight:700;">Code Version</div>',
            '<div style="padding:.75rem 1rem;font-weight:700;">Ground Truth</div>',
            '<div style="padding:.75rem 1rem;font-weight:700;">AI Generated</div>',
            '<div style="padding:.75rem 1rem;font-weight:700;">Doctor as LLM</div>',
            '<div style="padding:.75rem 1rem;font-weight:700;">OCR Time</div>',
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
        for (gen_time, code_ver, gt_url, ai_url, doc_url, ocr_start, ocr_end, total_tokens, input_tokens, output_tokens) in page_rows:
        # Find source item in outputs to get label/ai_key for metrics lookup
            src = next((it for it in outputs if (it.get('ai_url') == ai_url) or (it.get('doctor_url') == doc_url)), None)

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

            # Calculate OCR duration - use metrics data if available, otherwise use row data
            if met:
                ocr_duration = calculate_ocr_duration(met.get('ocr_start_time'), met.get('ocr_end_time'))
            else:
                ocr_duration = calculate_ocr_duration(ocr_start, ocr_end)

            gt_dl = dl_link(gt_url)
            ai_dl = dl_link(ai_url)
            doc_dl = dl_link(doc_url)
            # Show Ground Truth last modified date from assets if available
            gt_lm_iso = (assets or {}).get('ground_truth_last_modified')
            if isinstance(gt_lm_iso, str):
                try:
                    from datetime import datetime as _dt
                    _dt_obj = _dt.fromisoformat(gt_lm_iso)
                    gt_text = _dt_obj.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    gt_text = extract_date_from_url(gt_url)
            else:
                gt_text = extract_date_from_url(gt_url)
            gt_link = f'<a href="{gt_dl}" class="st-a" download>{gt_text}</a>' if gt_dl else '<span style="opacity:.6;">—</span>'
            ai_link = f'<a href="{ai_dl}" class="st-a" download>{extract_date_from_url(ai_url)}</a>' if ai_dl else '<span style="opacity:.6;">—</span>'
            doc_link = f'<a href="{doc_dl}" class="st-a" download>{extract_date_from_url(doc_url)}</a>' if doc_dl else '<span style="opacity:.6;">—</span>'

            table_html.append('<div class="history-table" style="border-bottom:1px solid rgba(255,255,255,0.06);">')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;">{gen_time}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;">{code_ver}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;">{gt_link}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;">{ai_link}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;">{doc_link}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{ocr_duration}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{total_tokens}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{input_tokens}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{output_tokens}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec2dur}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec3dur}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec4dur}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec9dur}</div>')
            table_html.append('</div>')

    # Close the table container
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
            # Use backend proxy to avoid CORS issues
            proxy_url = f"{backend}/proxy/pdf?url=" + quote(gt_effective_pdf_url, safe="")
            components.html(
                f"""
                <div id=\"gt_pdf_container\" style=\"height:{iframe_h}px; overflow:auto; border:1px solid rgba(255,255,255,0.12); border-radius:10px;\"></div>
                <script src=\"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js\"></script>
                <script>
                  const pdfjsLib = window['pdfjs-dist/build/pdf'];
                  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
                  async function render(url, containerId) {{
                    const container = document.getElementById(containerId);
                    container.innerHTML='';
                    try {{
                      const res = await fetch(url, {{ method: 'GET', mode: 'cors', headers: {{ 'Accept': 'application/pdf' }} }});
                      if (!res.ok) throw new Error('HTTP ' + res.status);
                      const buf = await res.arrayBuffer();
                      const loadingTask = pdfjsLib.getDocument({{ data: buf }});
                      const pdf = await loadingTask.promise;
                      for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {{
                        const page = await pdf.getPage(pageNum);
                        const viewport = page.getViewport({{ scale: 1 }});
                        const canvas = document.createElement('canvas');
                        const context = canvas.getContext('2d');
                        canvas.style.display = 'block';
                        canvas.style.width = '100%';
                        const scale = container.clientWidth / viewport.width;
                        const scaledViewport = page.getViewport({{ scale }});
                        canvas.width = Math.floor(scaledViewport.width);
                        canvas.height = Math.floor(scaledViewport.height);
                        container.appendChild(canvas);
                        await page.render({{ canvasContext: context, viewport: scaledViewport }}).promise;
                      }}
                    }} catch(e) {{
                      const div = document.createElement('div');
                      div.textContent = 'Failed to render PDF.';
                      div.style.opacity = '0.8';
                      container.appendChild(div);
                    }}
                  }}
                  render('{proxy_url}', 'gt_pdf_container');
                  window.addEventListener('resize', () => render('{proxy_url}', 'gt_pdf_container'));
                </script>
                """,
                height=iframe_h + 16,
            )
            st.markdown(f"<div style=\"margin-top: 0.5rem; text-align: center;\"><a href=\"{proxy_url}\" target=\"_blank\" style=\"color: #93c5fd; text-decoration: none; font-size: 0.9rem;\">📥 Download PDF</a></div>", unsafe_allow_html=True)
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
        # Prefer PDF AI outputs (dropdown like History)
        from urllib.parse import urlparse
        def _is_pdf(u: str | None) -> bool:
            if not isinstance(u, str) or not u:
                return False
            try:
                return urlparse(u).path.lower().endswith('.pdf')
            except Exception:
                return u.lower().endswith('.pdf')
        _pdf_outputs = [o for o in outputs if _is_pdf(o.get("ai_url"))]
        if not _pdf_outputs:
            _pdf_outputs = [o for o in outputs if _is_pdf(o.get("ai_url")) or _is_pdf(o.get("doctor_url"))]
        if not _pdf_outputs:
            _pdf_outputs = outputs
        # Dropdown labels
        labels = [o.get("label") or (o.get("ai_key") or "").split("/")[-1] for o in _pdf_outputs]
        if labels:
            # Reset selection when changing cases, and default to latest (index 0)
            if st.session_state.get("__results_case_id") != case_id:
                st.session_state["__results_case_id"] = case_id
                st.session_state["results_ai_label"] = None
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
            sel_ai = _pdf_outputs[0] if _pdf_outputs else None
        ai_effective_pdf_url = None
        if sel_ai and sel_ai.get("ai_url"):
            # Use backend proxy to avoid CORS issues
            proxy_url = f"{backend}/proxy/pdf?url=" + quote(sel_ai['ai_url'], safe="")
            components.html(
                f"""
                <div id=\"ai_pdf_container\" style=\"height:{iframe_h}px; overflow:auto; border:1px solid rgba(255,255,255,0.12); border-radius:10px;\"></div>
                <script src=\"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js\"></script>
                <script>
                  const pdfjsLib = window['pdfjs-dist/build/pdf'];
                  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
                  async function render(url, containerId) {{
                    const container = document.getElementById(containerId);
                    container.innerHTML='';
                    try {{
                      const res = await fetch(url, {{ method: 'GET', mode: 'cors', headers: {{ 'Accept': 'application/pdf' }} }});
                      if (!res.ok) throw new Error('HTTP ' + res.status);
                      const buf = await res.arrayBuffer();
                      const loadingTask = pdfjsLib.getDocument({{ data: buf }});
                      const pdf = await loadingTask.promise;
                      for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {{
                        const page = await pdf.getPage(pageNum);
                        const viewport = page.getViewport({{ scale: 1 }});
                        const canvas = document.createElement('canvas');
                        const context = canvas.getContext('2d');
                        canvas.style.display = 'block';
                        canvas.style.width = '100%';
                        const scale = container.clientWidth / viewport.width;
                        const scaledViewport = page.getViewport({{ scale }});
                        canvas.width = Math.floor(scaledViewport.width);
                        canvas.height = Math.floor(scaledViewport.height);
                        container.appendChild(canvas);
                        await page.render({{ canvasContext: context, viewport: scaledViewport }}).promise;
                      }}
                    }} catch(e) {{
                      const div = document.createElement('div');
                      div.textContent = 'Failed to render PDF.';
                      div.style.opacity = '0.8';
                      container.appendChild(div);
                    }}
                  }}
                  render('{proxy_url}', 'ai_pdf_container');
                  window.addEventListener('resize', () => render('{proxy_url}', 'ai_pdf_container'));
                </script>
                """,
                height=iframe_h + 16,
            )
            st.markdown(f"<div style=\"margin-top: 0.5rem; text-align: center;\"><a href=\"{proxy_url}\" target=\"_blank\" style=\"color: #93c5fd; text-decoration: none; font-size: 0.9rem;\">📥 Download PDF</a></div>", unsafe_allow_html=True)
            ai_effective_pdf_url = sel_ai["ai_url"]
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
            # Use backend proxy to avoid CORS issues
            proxy_url = f"{backend}/proxy/pdf?url=" + quote(sel_ai['doctor_url'], safe="")
            components.html(
                f"""
                <div id=\"doc_pdf_container\" style=\"height:{iframe_h}px; overflow:auto; border:1px solid rgba(255,255,255,0.12); border-radius:10px;\"></div>
                <script src=\"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js\"></script>
                <script>
                  const pdfjsLib = window['pdfjs-dist/build/pdf'];
                  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
                  async function render(url, containerId) {{
                    const container = document.getElementById(containerId);
                    container.innerHTML='';
                    try {{
                      const res = await fetch(url, {{ method: 'GET', mode: 'cors', headers: {{ 'Accept': 'application/pdf' }} }});
                      if (!res.ok) throw new Error('HTTP ' + res.status);
                      const buf = await res.arrayBuffer();
                      const loadingTask = pdfjsLib.getDocument({{ data: buf }});
                      const pdf = await loadingTask.promise;
                      for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {{
                        const page = await pdf.getPage(pageNum);
                        const viewport = page.getViewport({{ scale: 1 }});
                        const canvas = document.createElement('canvas');
                        const context = canvas.getContext('2d');
                        canvas.style.display = 'block';
                        canvas.style.width = '100%';
                        const scale = container.clientWidth / viewport.width;
                        const scaledViewport = page.getViewport({{ scale }});
                        canvas.width = Math.floor(scaledViewport.width);
                        canvas.height = Math.floor(scaledViewport.height);
                        container.appendChild(canvas);
                        await page.render({{ canvasContext: context, viewport: scaledViewport }}).promise;
                      }}
                    }} catch(e) {{
                      const div = document.createElement('div');
                      div.textContent = 'Failed to render PDF.';
                      div.style.opacity = '0.8';
                      container.appendChild(div);
                    }}
                  }}
                  render('{proxy_url}', 'doc_pdf_container');
                  window.addEventListener('resize', () => render('{proxy_url}', 'doc_pdf_container'));
                </script>
                """,
                height=iframe_h + 16,
            )
            st.markdown(f"<div style=\"margin-top: 0.5rem; text-align: center;\"><a href=\"{proxy_url}\" target=\"_blank\" style=\"color: #93c5fd; text-decoration: none; font-size: 0.9rem;\">📥 Download PDF</a></div>", unsafe_allow_html=True)
            doc_effective_pdf_url = sel_ai["doctor_url"]
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