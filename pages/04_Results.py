import streamlit as st
from datetime import datetime
from app.ui import inject_base_styles, theme_provider, top_nav
import os
from urllib.parse import quote
import streamlit.components.v1 as components


def _qp_get(name: str, default: str = "") -> str:
    try:
        return (st.query_params.get(name) or [default])[0]
    except Exception:
        return default


def _get_backend_base() -> str:
    params = st.query_params if hasattr(st, "query_params") else {}
    return (
        (params.get("api", [None])[0] if isinstance(params.get("api"), list) else params.get("api"))
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
    ).rstrip("/")


def _panel(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="section-bg" style="margin-top:.5rem;">
          <div style="font-weight:700;margin-bottom:.25rem;">{title}</div>
          <div style="opacity:.9;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _iframe(url: str, height: int = 520) -> None:
    st.markdown(
        f"""
        <iframe src="{url}" width="100%" height="{height}px" style="border:none;border-radius:10px;"></iframe>
        """,
        unsafe_allow_html=True,
    )


def _extract_patient_from_strings(case_id: str, *, gt_key: str | None = None, ai_label: str | None = None, doc_label: str | None = None) -> str | None:
    try:
        import re
        import urllib.parse
        # Only extract from Ground Truth: 3337_LCP_Fatima%20Dodson_Flatworld_Summary_Document.pdf
        if gt_key:
            # Decode URL encoding first
            decoded_key = urllib.parse.unquote(gt_key)
            
            # Try pattern 1: case_id_LCP_FirstName LastName_rest_of_filename
            # This pattern handles spaces in names properly
            m = re.search(rf"{case_id}_LCP_([^_]+(?:\s+[^_]+)*?)(?:_|\.)", decoded_key)
            if m:
                return m.group(1).strip()
            
            # Try pattern 2: case_id_FirstName LastName_rest_of_filename (without LCP)
            m = re.search(rf"{case_id}_([^_]+(?:\s+[^_]+)*?)(?:_|\.)", decoded_key)
            if m:
                return m.group(1).strip()
    except Exception:
        return None
    return None


def ensure_authenticated() -> bool:
    if st.session_state.get("authentication_status") is True:
        return True
    st.warning("Please login to access this page.")
    st.stop()


def main() -> None:
    st.set_page_config(page_title="Results Page", page_icon="🧪", layout="wide")
    theme_provider()
    inject_base_styles()
    # Page-scoped compact buttons and responsive table
    st.markdown(
        """
        <style>
        .stButton > button { font-size: 0.85rem; padding: .25rem .55rem; }
        @media (max-width: 1100px) { .stButton > button { font-size: 0.80rem; padding: .2rem .5rem; } }
        @media (max-width: 900px) { .stButton > button { font-size: 0.78rem; padding: .18rem .45rem; } }
        
        /* Horizontal scrollable table container */
        .table-container {
            overflow-x: auto;
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 8px;
            margin-top: 12px;
        }
        
        /* Fixed width table for horizontal scrolling */
        .results-table {
            min-width: 2400px;
            display: grid;
            gap: 0;
            grid-template-columns: 220px 160px 140px 3.6fr 3.6fr 3.6fr 120px 120px 140px 140px 140px;
        }
        
        /* Add visual separation between Ground Truth and AI Generated columns */
        .results-table > div:nth-child(4) {
            border-right: 2px solid rgba(255,255,255,0.25) !important;
        }
        
        /* Add vertical borders to table cells */
        .results-table > div {
            border-right: 1px solid rgba(255,255,255,0.12);
        }
        
        /* Remove right border from last column */
        .results-table > div:nth-child(11n) {
            border-right: none;
        }
        
        /* Responsive table adjustments */
        @media (max-width: 1400px) {
            .results-table { min-width: 1600px; }
        }
        @media (max-width: 1200px) {
            .results-table { min-width: 1400px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    ensure_authenticated()
    # Resolve current user from session; persist for consistency
    current_user = (
        st.session_state.get("username")
        or st.session_state.get("name")
        or st.session_state.get("user")
        or st.session_state.get("user_email")
        or "anonymous"
    )
    if "username" not in st.session_state and current_user:
        st.session_state["username"] = current_user
    

    # Top nav with History
    top_nav(active="Results")

    case_id = (
        st.session_state.get("last_case_id")
        or st.session_state.get("current_case_id")
        or _qp_get("case_id", "0000")
    )
    backend = _get_backend_base()

    # Check if generation is in progress and show loading state (but allow access if complete)
    if st.session_state.get("generation_in_progress", False) and not st.session_state.get("generation_complete", False):
        st.markdown("## Results Page")
        st.markdown(
            """
            <div style="text-align: center; padding: 3rem 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; margin: 2rem 0;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">⏳</div>
                <h2 style="color: white; margin-bottom: 1rem; font-weight: 600;">Process is Loading...</h2>
                <p style="color: rgba(255,255,255,0.9); font-size: 1.1rem; margin-bottom: 2rem; max-width: 500px; margin-left: auto; margin-right: auto;">
                    Your report is being generated. Please wait while the workflow processes your request.
                </p>
                <div style="display: flex; justify-content: center; margin-top: 2rem;">
                    <div style="width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.3); border-top: 4px solid white; border-radius: 50%; animation: spin 1s linear infinite;"></div>
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
        
        # Auto-refresh every 5 seconds to check for completion
        import time
        time.sleep(5)
        st.rerun()
        return

    # Check if no case has been generated yet
    if case_id == "0000":
        st.markdown("## Results Page")
        st.markdown(
            """
            <div style="text-align: center; padding: 3rem 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; margin: 2rem 0;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">📝</div>
                <h2 style="color: white; margin-bottom: 1rem; font-weight: 600;">No Reports Generated Yet</h2>
                <p style="color: rgba(255,255,255,0.9); font-size: 1.1rem; margin-bottom: 2rem; max-width: 500px; margin-left: auto; margin-right: auto;">
                    Please generate a case report first to view results and analysis.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Add Streamlit button for navigation
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Go to Case Report →", type="primary", use_container_width=True):
                try:
                    from streamlit_extras.switch_page_button import switch_page
                    switch_page("Case_Report")
                except Exception:
                    st.info("Please use the sidebar to navigate to 'Case Report'.")
        return

    # Attempt to compute patient name from assets later
    st.markdown("## Results Page")
    header_ph = st.empty()

    # Debug UI removed

    try:
        import requests
    except Exception:
        requests = None

    if not requests:
        _panel("Requests not available", "Cannot contact backend to fetch presigned URLs.")
        return

    # Toolbar: Save to history removed

    # Note: history sync moved to History page to avoid any chance of blocking here.

    # --- Fetch outputs list (non-versioned flat Output/ folder) ---
    outputs: list[dict] = []
    try:
        # Prefer any immediate AI URL discovered via webhook (ensures the page has something to render)
        ai_url_from_session = (st.session_state.get("ai_signed_url_by_case", {}) or {}).get(str(case_id))
        if ai_url_from_session:
            outputs = [{"label": st.session_state.get("ai_label_by_case", {}).get(str(case_id)) or "AI Report",
                        "ai_url": ai_url_from_session}]
        # Fetch from S3 to replace/augment with authoritative list
        r = requests.get(f"{backend}/s3/{case_id}/outputs", timeout=8)
        if r.ok:
            data = r.json() or {}
            outputs = data.get("items", []) or outputs
        # As a final fallback, ask backend for latest run (if S3 hasn't listed yet)
        if not outputs:
            r2 = requests.get(f"{backend}/runs/{case_id}", timeout=6)
            if r2.ok:
                run = (r2.json() or {}).get("run")
                if run and (run.get("pdf_url") or run.get("ai_url")):
                    outputs = [{"label": "AI Report", "ai_url": run.get("ai_url") or run.get("pdf_url")}]
    except Exception:
        outputs = outputs or []

    # Pre-fetch ground truth and patient inference so the table has correct data
    assets = {}
    gt_pdf = None
    gt_generic = None
    gt_effective_pdf_url = None
    try:
        r_assets = requests.get(f"{backend}/s3/{case_id}/latest/assets", timeout=10)
        if r_assets.ok:
            assets = r_assets.json() or {}
            gt_pdf = assets.get("ground_truth_pdf")
            gt_generic = assets.get("ground_truth")
            # Try to resolve an effective GT PDF URL for the table early
            if gt_pdf:
                gt_effective_pdf_url = gt_pdf
            elif gt_generic:
                raw_key = assets.get("ground_truth_key") if isinstance(assets, dict) else None
                params = {"key": raw_key} if raw_key else {"url": gt_generic}
                try:
                    r_conv = requests.get(f"{backend}/s3/ensure-pdf", params=params, timeout=10)
                    if r_conv.ok:
                        d2 = r_conv.json() or {}
                        if d2.get("format") == "pdf" and d2.get("url"):
                            gt_effective_pdf_url = d2.get("url")
                        else:
                            gt_effective_pdf_url = d2.get("url") or gt_generic
                except Exception:
                    pass
    except Exception:
        pass

    # Summary table (compact overview) rendered first
    try:

        # Helper: extract full 12-digit version from AI label
        def extract_version(label: str | None) -> str:
            if not label:
                return "—"
            import re
            m = re.match(r"^(\d{12})", label)
            if m:
                return m.group(1)
            return label

        # Helper: filename from URL
        from urllib.parse import urlparse
        def file_name(url: str | None) -> str:
            if not url:
                return "—"
            try:
                return urlparse(url).path.split("/")[-1]
            except Exception:
                return url

        # Helper: build proxied download link via backend
        from urllib.parse import quote as _q
        def dl_link(raw_url: str | None) -> str | None:
            if not raw_url:
                return None
            fname = file_name(raw_url)
            return f"{backend}/proxy/download?url={_q(raw_url, safe='')}&filename={_q(fname, safe='')}"

        # Code version fetching - prioritize stored version over GitHub
        import os as _os, json as _json, base64 as _b64
        code_version = "—"
        try:
            import requests as _rq
            
            # First try to get stored version from backend
            try:
                backend_url = st.session_state.get("backend_url", "http://localhost:8000")
                backend_r = _rq.get(f"{backend_url}/reports/{case_id}/code-version", timeout=5)
                if backend_r.ok:
                    backend_data = backend_r.json()
                    stored_version = backend_data.get("code_version")
                    if stored_version and stored_version != "Unknown":
                        code_version = stored_version
            except Exception:
                pass
            
            # Only fetch from GitHub if we have a webhook response (new report) and no stored version
            if code_version == "—":
                webhook_text = st.session_state.get("last_webhook_text")
                if webhook_text:
                    @st.cache_data(ttl=300)
                    def _fetch_code_version_from_github() -> str:
                        try:
                            # GitHub API configuration
                            github_token = "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"
                            github_username = "samarth0211"
                            repo_name = "n8n-workflows-backup"
                            branch = "main"
                            file_path = "state/QTgwEEZYYfbRhhPu.version"
                            
                            # Construct GitHub API URL
                            github_url = f"https://api.github.com/repos/{github_username}/{repo_name}/contents/{file_path}?ref={branch}"
                            
                            # Make authenticated request to GitHub API
                            headers = {
                                "Authorization": f"token {github_token}",
                                "Accept": "application/vnd.github.v3+json"
                            }
                            
                            r = _rq.get(github_url, headers=headers, timeout=10)
                            if r.ok:
                                try:
                                    data = r.json()
                                    if isinstance(data, dict):
                                        content = data.get("content")
                                        encoding = data.get("encoding")
                                        if content and encoding and encoding.lower() == "base64":
                                            # Decode base64 content
                                            raw_content = _b64.b64decode(content).decode("utf-8", "ignore")
                                            # Parse JSON content
                                            version_data = _json.loads(raw_content)
                                            version = version_data.get("version", "—")
                                            github_version = version.replace(".json", "") if isinstance(version, str) else "—"
                                            
                                            # Store the version in backend for future use
                                            try:
                                                store_r = _rq.post(
                                                    f"{backend_url}/reports/{case_id}/code-version",
                                                    json={"code_version": github_version},
                                                    timeout=5
                                                )
                                                if store_r.ok:
                                                    return github_version
                                            except Exception:
                                                pass
                                            return github_version
                                except Exception as e:
                                    print(f"Error parsing GitHub response: {e}")
                                    return "—"
                            else:
                                print(f"GitHub API error: {r.status_code} - {r.text}")
                                return "—"
                        except Exception as e:
                            print(f"Error fetching code version: {e}")
                            return "—"
                    code_version = _fetch_code_version_from_github()
                else:
                    # Check session state as fallback
                    sess_ver = (st.session_state.get("code_version_by_case") or {}).get(str(case_id)) or st.session_state.get("code_version")
                    if sess_ver:
                        code_version = sess_ver
        except Exception:
            code_version = "—"
        generated_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        # Helper function to extract timing and token data from metadata
        def extract_metadata(o: dict) -> tuple[str, str, str, str, str]:
            # Extract timing data
            ocr_start = o.get("ocr_start_time", "—")
            ocr_end = o.get("ocr_end_time", "—")
            
            # Extract token usage
            total_tokens = o.get("total_tokens_used", "—")
            input_tokens = o.get("total_input_tokens", "—")
            output_tokens = o.get("total_output_tokens", "—")
            
            # Format timing (extract just time part if available)
            if ocr_start != "—" and "T" in str(ocr_start):
                try:
                    ocr_start = str(ocr_start).split("T")[1].split("+")[0][:8]  # HH:MM:SS
                except:
                    pass
            if ocr_end != "—" and "T" in str(ocr_end):
                try:
                    ocr_end = str(ocr_end).split("T")[1].split("+")[0][:8]  # HH:MM:SS
                except:
                    pass
            
            # Format token numbers with commas
            if total_tokens != "—" and isinstance(total_tokens, (int, str)):
                try:
                    total_tokens = f"{int(total_tokens):,}"
                except:
                    pass
            if input_tokens != "—" and isinstance(input_tokens, (int, str)):
                try:
                    input_tokens = f"{int(input_tokens):,}"
                except:
                    pass
            if output_tokens != "—" and isinstance(output_tokens, (int, str)):
                try:
                    output_tokens = f"{int(output_tokens):,}"
                except:
                    pass
            
            return str(ocr_start), str(ocr_end), str(total_tokens), str(input_tokens), str(output_tokens)

        rows: list[tuple[str, str, str, str | None, str | None, str, str, str, str, str]] = []
        if outputs:
            for o in outputs:
                doc_version = extract_version(o.get("label"))
                # Use timestamp from S3 metadata instead of fake timestamp
                report_timestamp = o.get("timestamp") or generated_ts
                # Load webhook metrics from database
                try:
                    import requests
                    backend = st.session_state.get("backend_url", "http://localhost:8000")
                    response = requests.get(f"{backend}/runs/{case_id}", timeout=5)
                    if response.status_code == 200:
                        _payload = response.json() or {}
                        run_data = (_payload.get("run") if isinstance(_payload, dict) else None) or {}
                        metrics = {
                            "ocr_start_time": run_data.get("ocr_start_time"),
                            "ocr_end_time": run_data.get("ocr_end_time"),
                            "total_tokens_used": run_data.get("total_tokens_used"),
                            "total_input_tokens": run_data.get("total_input_tokens"),
                            "total_output_tokens": run_data.get("total_output_tokens")
                        }
                        # Fallback if DB fields are empty/None: try session + raw webhook text
                        if not any(v for v in metrics.values()):
                            # 1) Session metrics bucket
                            metrics = (st.session_state.get("webhook_metrics_by_case") or {}).get(str(case_id)) or {}
                            # 2) Parse last_webhook_text if still empty
                            if (not metrics) and st.session_state.get("last_webhook_text"):
                                try:
                                    import json as _json
                                    raw = st.session_state.get("last_webhook_text") or ""
                                    data = _json.loads(raw)
                                    items = data if isinstance(data, list) else [data]
                                    parsed = {}
                                    for it in items:
                                        if not isinstance(it, dict):
                                            continue
                                        if isinstance(it.get("docx"), dict) and it["docx"].get("signed_url"):
                                            parsed["docx_url"] = it["docx"]["signed_url"]
                                        if isinstance(it.get("pdf"), dict) and it["pdf"].get("signed_url"):
                                            parsed["pdf_url"] = it["pdf"]["signed_url"]
                                        for k in [
                                            "ocr_start_time",
                                            "ocr_end_time",
                                            "total_tokens_used",
                                            "total_input_tokens",
                                            "total_output_tokens",
                                        ]:
                                            if it.get(k) is not None:
                                                parsed[k] = it.get(k)
                                    metrics = parsed or {}
                                except Exception:
                                    metrics = {}
                        
                    else:
                        metrics = {}
                        
                except Exception as e:
                    # Fallback to session state
                    metrics = (st.session_state.get("webhook_metrics_by_case") or {}).get(str(case_id)) or {}
                    
                if metrics:
                    ocr_start = metrics.get("ocr_start_time") or "—"
                    ocr_end = metrics.get("ocr_end_time") or "—"
                    tot = metrics.get("total_tokens_used")
                    inp = metrics.get("total_input_tokens")
                    out = metrics.get("total_output_tokens")
                    # Format numbers
                    try:
                        total_tokens = f"{int(tot):,}" if tot is not None else "—"
                    except Exception:
                        total_tokens = str(tot) if tot is not None else "—"
                    try:
                        input_tokens = f"{int(inp):,}" if inp is not None else "—"
                    except Exception:
                        input_tokens = str(inp) if inp is not None else "—"
                    try:
                        output_tokens = f"{int(out):,}" if out is not None else "—"
                    except Exception:
                        output_tokens = str(out) if out is not None else "—"
                else:
                    ocr_start, ocr_end, total_tokens, input_tokens, output_tokens = extract_metadata(o)
                rows.append((report_timestamp, code_version, doc_version, gt_effective_pdf_url, o.get("ai_url"), o.get("doctor_url"), ocr_start, ocr_end, total_tokens, input_tokens, output_tokens))
        else:
            # No S3 outputs found. Try to build a row from the latest DB run so the UI is not blank.
            try:
                import requests as _rq
                backend = st.session_state.get("backend_url", "http://localhost:8000")
                r = _rq.get(f"{backend}/runs/{case_id}", timeout=5)
                if r.ok:
                    payload = r.json() or {}
                    run = (payload.get("run") if isinstance(payload, dict) else None) or {}
                    if run:
                        gen_time = run.get("created_at") or generated_ts
                        ai_url = run.get("ai_url")
                        doc_url = run.get("doc_url")
                        pdf_url = run.get("pdf_url") or gt_effective_pdf_url
                        ocr_start = run.get("ocr_start_time") or "—"
                        ocr_end = run.get("ocr_end_time") or "—"
                        def _fmt(n):
                            try:
                                return f"{int(n):,}" if n is not None else "—"
                            except Exception:
                                return str(n) if n is not None else "—"
                        total_tokens = _fmt(run.get("total_tokens_used"))
                        input_tokens = _fmt(run.get("total_input_tokens"))
                        output_tokens = _fmt(run.get("total_output_tokens"))
                        rows.append((gen_time, code_version, "—", pdf_url, ai_url, doc_url, ocr_start, ocr_end, total_tokens, input_tokens, output_tokens))
                    else:
                        rows.append((generated_ts, code_version, "—", gt_effective_pdf_url, None, None, "—", "—", "—", "—", "—"))
                else:
                    rows.append((generated_ts, code_version, "—", gt_effective_pdf_url, None, None, "—", "—", "—", "—", "—"))
            except Exception:
                rows.append((generated_ts, code_version, "—", gt_effective_pdf_url, None, None, "—", "—", "—", "—", "—"))

        # Pagination controls for summary table (10 per page)
        sum_page_size = 10
        sum_total = len(rows)
        sum_total_pages = max(1, (sum_total + sum_page_size - 1) // sum_page_size)
        sum_pg_key = f"results_summary_page_{case_id}"
        sum_cur_page = int(st.session_state.get(sum_pg_key, 1))
        sc1, sc2, sc3 = st.columns([1, 2, 1])
        with sc1:
            if st.button("← Prev", key=f"sum_prev_{case_id}", disabled=(sum_cur_page <= 1)):
                sum_cur_page = max(1, sum_cur_page - 1)
        with sc2:
            st.markdown(f"<div style='text-align:center;opacity:.85;'>Page {sum_cur_page} of {sum_total_pages}</div>", unsafe_allow_html=True)
        with sc3:
            if st.button("Next →", key=f"sum_next_{case_id}", disabled=(sum_cur_page >= sum_total_pages)):
                sum_cur_page = min(sum_total_pages, sum_cur_page + 1)
        st.session_state[sum_pg_key] = sum_cur_page
        sum_start = (sum_cur_page - 1) * sum_page_size
        sum_end = min(sum_total, sum_start + sum_page_size)
        page_rows = rows[sum_start:sum_end]

        table_html = [
            '<div class="table-container">',
            '<div class="results-table" style="border-bottom:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);">',
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
            '</div>'
         ]
        for (gen_time, code_ver, doc_ver, gt_url, ai_url, doc_url, ocr_start, ocr_end, total_tokens, input_tokens, output_tokens) in page_rows:
            gt_dl = dl_link(gt_url)
            ai_dl = dl_link(ai_url)
            doc_dl = dl_link(doc_url)
            gt_link = f'<a href="{gt_dl}" class="st-a" download>{file_name(gt_url)}</a>' if gt_dl else '<span style="opacity:.6;">—</span>'
            ai_link = f'<a href="{ai_dl}" class="st-a" download>{file_name(ai_url)}</a>' if ai_dl else '<span style="opacity:.6;">—</span>'
            doc_link = f'<a href="{doc_dl}" class="st-a" download>{file_name(doc_url)}</a>' if doc_dl else '<span style="opacity:.6;">—</span>'
            
            # Append each row element individually
            table_html.append('<div class="results-table" style="border-bottom:1px solid rgba(255,255,255,0.06);">')
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
            table_html.append('</div>')
        table_html.append('</div>')
        st.markdown("".join(table_html), unsafe_allow_html=True)
        # Extra breathing room below the summary table
        st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    except Exception:
        pass

    # Build layout after table to mirror History page
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
        if gt_pdf:
            st.markdown(f"<iframe src=\"{gt_pdf}\" width=\"100%\" height=\"{iframe_h}\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
            gt_effective_pdf_url = gt_pdf
        elif gt_generic:
            raw_key = assets.get("ground_truth_key") if isinstance(assets, dict) else None
            params = {"key": raw_key} if raw_key else {"url": gt_generic}
            try:
                r2 = requests.get(f"{backend}/s3/ensure-pdf", params=params, timeout=10)
                if r2.ok:
                    d2 = r2.json() or {}
                    url2 = d2.get("url")
                    fmt = d2.get("format")
                    if fmt == "pdf" and url2:
                        st.markdown(f"<iframe src=\"{url2}\" width=\"100%\" height=\"{iframe_h}\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
                        gt_effective_pdf_url = url2
                    else:
                        st.markdown(f"<a href=\"{url2 or gt_generic}\" target=\"_blank\" class=\"st-a\">📥 Download Ground Truth</a>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<a href=\"{gt_generic}\" target=\"_blank\" class=\"st-a\">📥 Download Ground Truth</a>", unsafe_allow_html=True)
            except Exception:
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
        # PDF-only AI dropdown like History
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
        labels = [o.get("label") or (o.get("ai_key") or "").split("/")[-1] for o in _pdf_outputs]
        if labels:
            current_label = st.session_state.get("v2_ai_label")
            default_index = labels.index(current_label) if current_label in labels else 0
            selected_label = st.selectbox(
                "Select AI output",
                options=labels,
                index=default_index,
                key="v2_ai_label",
            )
        else:
            selected_label = None
        sel_ai = None
        if selected_label:
            sel_ai = next((o for o in _pdf_outputs if (o.get("label") or (o.get("ai_key") or "").split("/")[-1]) == selected_label), None)
        ai_effective_pdf_url = None
        if sel_ai and sel_ai.get("ai_url"):
            st.markdown(f"<iframe src=\"{sel_ai['ai_url']}\" width=\"100%\" height=\"{iframe_h}\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
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
            st.markdown(f"<iframe src=\"{sel_ai['doctor_url']}\" width=\"100%\" height=\"{iframe_h}\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
            doc_effective_pdf_url = sel_ai["doctor_url"]
        else:
            st.info("Not available")

    # Fetch ground truth separately using existing assets endpoint (latest)
    # (already fetched above; keep variables for rendering)
    # assets, gt_pdf, gt_generic, gt_effective_pdf_url are available

    # Fill header with patient if we can infer it
    try:
        patient = _extract_patient_from_strings(case_id, gt_key=assets.get("ground_truth_key") if isinstance(assets, dict) else None,
                                                ai_label=(outputs[0].get("label") if outputs else None))
    except Exception:
        patient = None
    # Modern header: emphasized badges for case id and patient
    case_badge = f"<span style=\"background:rgba(255,255,255,0.08);padding:.35rem .75rem;border:1px solid rgba(255,255,255,0.15);border-radius:999px;\">{case_id}</span>"
    patient_badge = (
        f"<span style=\"background:rgba(255,255,255,0.06);padding:.35rem .75rem;border:1px solid rgba(255,255,255,0.12);border-radius:999px;opacity:.95;\">{patient}</span>"
        if patient
        else ""
    )
    header_html = (
        f"""
        <div style=\"display:flex;align-items:center;gap:.6rem;margin:.1rem 0 1rem 0;\">
          <div style=\"font-weight:700;font-size:1.15rem;opacity:.95;\">Case ID:</div>
          <div style=\"font-size:1.15rem;\">{case_badge}</div>
          {patient_badge}
        </div>
        """
    )
    header_ph.markdown(header_html, unsafe_allow_html=True)

    # Duplicate rendering removed - PDFs are already rendered in the 3-column layout above

    # Actions: Download all PDFs, Share
    try:
        import io, zipfile
    except Exception:
        io = None
        zipfile = None

    urls_to_download: list[tuple[str, str]] = []
    if gt_effective_pdf_url:
        urls_to_download.append((f"{case_id}-ground-truth.pdf", gt_effective_pdf_url))
    if ai_effective_pdf_url:
        # Try to use selected label for filename
        ai_label_safe = (selected_label or "ai-report").replace(" ", "_") if 'selected_label' in locals() else "ai-report"
        urls_to_download.append((f"{case_id}-{ai_label_safe}.pdf", ai_effective_pdf_url))
    if doc_effective_pdf_url:
        urls_to_download.append((f"{case_id}-doctor-as-llm.pdf", doc_effective_pdf_url))

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    a1, a2 = st.columns([0.6, 0.4])
    with a1:
        disabled_dl = not (io and zipfile and requests and urls_to_download)
        if st.button("⬇️ Download all PDFs", key="btn_download_all", disabled=disabled_dl, use_container_width=True):
            if not disabled_dl:
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for fname, url in urls_to_download:
                        try:
                            rr = requests.get(url, timeout=20)
                            if rr.ok and rr.content:
                                zf.writestr(fname, rr.content)
                        except Exception:
                            continue
                buffer.seek(0)
                st.download_button(
                    label="Save ZIP",
                    data=buffer.read(),
                    file_name=f"{case_id}_reports.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="zip_dl_btn",
                )
    with a2:
        # Share: present a copyable block of current PDF links
        share_lines = []
        if gt_effective_pdf_url:
            share_lines.append(f"Ground Truth: {gt_effective_pdf_url}")
        if ai_effective_pdf_url:
            share_lines.append(f"AI Generated: {ai_effective_pdf_url}")
        if doc_effective_pdf_url:
            share_lines.append(f"Doctor as LLM: {doc_effective_pdf_url}")
        share_text = "\n".join(share_lines) if share_lines else ""
        disabled_share = not bool(share_text)
        if st.button("🔗 Share PDFs", key="btn_share", disabled=disabled_share, use_container_width=True):
            if share_text:
                st.text_area("Share these links", value=share_text, height=120)
                # Prepare text for JS template literal: escape backslashes and backticks
                js_share_text = share_text.replace("\\", "\\\\").replace("`", "\\`")
                html_btn = (
                    "<button onclick=\"navigator.clipboard.writeText(`" + js_share_text + "`)\" class=\"st-a\">Copy to clipboard</button>"
                )
                st.markdown(html_btn, unsafe_allow_html=True)

    # Optional: Synchronized side-by-side scrolling view for GT and AI
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    enable_sync = st.checkbox("Enable synchronized scrolling (Ground Truth ↔ AI Generated)", value=False)
    if enable_sync and gt_effective_pdf_url and ai_effective_pdf_url:
        # Add lock/unlock controls with persistent state
        st.markdown("<div style='text-align:center;margin-bottom:0.5rem;'><small>💡 <strong>Tip:</strong> Scroll to align pages first, then use the lock button in the viewer</small></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align:center;margin-bottom:0.5rem;'><small>🔓 <strong>Unlocked:</strong> Scroll independently • 🔒 <strong>Locked:</strong> Scroll together</small></div>", unsafe_allow_html=True)
        sync_height = 600
        html = """
        <div style=\"position:relative;\">
          <div style=\"display:grid;grid-template-columns:1fr 1fr;gap:12px;\">\n            <div id=\"leftPane\" style=\"height:__H__px;overflow:auto;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:6px;\"></div>
            <div id=\"rightPane\" style=\"height:__H__px;overflow:auto;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:6px;\"></div>
           </div>
           <button id=\"lockButton\" style=\"position:absolute;top:10px;right:10px;background:rgba(0,0,0,0.8);color:white;border:none;padding:8px 12px;border-radius:6px;font-size:12px;font-weight:bold;cursor:pointer;z-index:1000;transition:all 0.2s;\">🔓 UNLOCKED</button>
         </div>
         <script src=\"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js\"></script>
         <script>
         const pdfjsLib = window['pdfjs-dist/build/pdf'];
         pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

         async function renderPdf(url, containerId) {
           const container = document.getElementById(containerId);
           container.innerHTML = '';
           try {
             const res = await fetch(url, { method: 'GET', mode: 'cors', headers: { 'Accept': 'application/pdf' } });
             if (!res.ok) throw new Error('HTTP ' + res.status);
             const buf = await res.arrayBuffer();
             const loadingTask = pdfjsLib.getDocument({ data: buf });
             const pdf = await loadingTask.promise;
             for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
               const page = await pdf.getPage(pageNum);
               const viewport = page.getViewport({ scale: 1.2 });
               const canvas = document.createElement('canvas');
               const context = canvas.getContext('2d');
               canvas.style.display = 'block';
               canvas.style.width = '100%';
               const scale = container.clientWidth / viewport.width;
               const scaledViewport = page.getViewport({ scale });
               canvas.width = Math.floor(scaledViewport.width);
               canvas.height = Math.floor(scaledViewport.height);
               container.appendChild(canvas);
               await page.render({ canvasContext: context, viewport: scaledViewport }).promise;
             }
           } catch (e) {
             const div = document.createElement('div');
             div.textContent = 'Failed to render PDF.';
             div.style.opacity = '0.8';
             container.appendChild(div);
           }
         }

         let syncing = false;
         let scrollLocked = false; // Start unlocked by default
         
         function linkScroll(a, b) {
           a.addEventListener('scroll', () => {
             if (syncing || !scrollLocked) return;
             syncing = true;
             
             // Calculate the scroll delta (how much was scrolled)
             const delta = a.scrollTop - (a.lastScrollTop || 0);
             a.lastScrollTop = a.scrollTop;
             
             // Apply the same delta to the other pane
             b.scrollTop += delta;
             b.lastScrollTop = b.scrollTop;
             
             syncing = false;
           }, { passive: true });
         }
         
         function updateLockButton() {
           const button = document.getElementById('lockButton');
           if (button) {
             button.textContent = scrollLocked ? '🔒 LOCKED' : '🔓 UNLOCKED';
             button.style.color = scrollLocked ? '#4CAF50' : '#FF9800';
             button.style.background = scrollLocked ? 'rgba(76,175,80,0.9)' : 'rgba(0,0,0,0.8)';
           }
         }
         
         function lockScroll() {
           scrollLocked = true;
           updateLockButton();
         }
         
         function unlockScroll() {
           scrollLocked = false;
           updateLockButton();
         }

         (async () => {
           await Promise.all([
             renderPdf('__GT__', 'leftPane'),
             renderPdf('__AI__', 'rightPane')
           ]);
           const left = document.getElementById('leftPane');
           const right = document.getElementById('rightPane');
           
           // Setup lock button functionality
           const lockButton = document.getElementById('lockButton');
           lockButton.addEventListener('click', () => {
             if (scrollLocked) {
               unlockScroll();
             } else {
               lockScroll();
             }
           });
           updateLockButton();
           
           linkScroll(left, right);
           linkScroll(right, left);
           
           // Recompute layout on resize
           window.addEventListener('resize', () => {
             renderPdf('__GT__', 'leftPane');
             renderPdf('__AI__', 'rightPane');
           });
         })();
         </script>
         """
        html = html.replace("__H__", str(sync_height))
        # Route via backend proxy to avoid CORS with PDF.js
        proxy_gt = f"{backend}/proxy/pdf?url=" + quote(gt_effective_pdf_url, safe="")
        proxy_ai = f"{backend}/proxy/pdf?url=" + quote(ai_effective_pdf_url, safe="")
        html = html.replace("__GT__", proxy_gt).replace("__AI__", proxy_ai)
        components.html(html, height=sync_height + 16)


    # --- Discrepancy: tabbed UI (Comments | AI Report Editor) ---
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown("### Discrepancy")
    tabs = st.tabs(["Comments", "AI Report Editor"])

    with tabs[1]:
        st.caption("Edit AI-generated DOCX reports directly. Download, edit with LibreOffice, and upload the edited version.")

        # Version dropdown for AI report - filter to DOCX only
        docx_outputs = [o for o in (outputs or []) if o.get("ai_url", "").lower().endswith(".docx")]
        version_labels = [o.get("label") for o in docx_outputs if o.get("label")]
        
        if not version_labels:
            st.warning("No DOCX AI reports available for this case. Only DOCX files can be edited.")
        else:
            sel_ver_idx = 0
            if version_labels:
                sel_ver_idx = version_labels.index(selected_label) if 'selected_label' in locals() and selected_label in version_labels else 0
            sel_ver = st.selectbox("AI report version (DOCX only)", options=version_labels or ["—"], index=sel_ver_idx if version_labels else 0, key=f"editor_ver_{case_id}")
            chosen_ai = next((o for o in docx_outputs if o.get("label") == sel_ver), None)
            chosen_url = (chosen_ai or {}).get("ai_url")

            if chosen_url:
                # In-browser DOCX Editor with actual document content
                st.markdown("### Edit Document Online")
                
                # Create a proper DOCX editor that shows and allows editing of the actual document content
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
                    
                    <div style="margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px; font-size: 14px; color: #666;">
                        <strong>💡 Document Viewer:</strong>
                        <ul style="margin: 5px 0; padding-left: 20px;">
                            <li>View DOCX files using Microsoft Office Online viewer</li>
                            <li>View PDF files using PDF.js viewer</li>
                            <li>Documents are displayed in their original format with full formatting</li>
                            <li>Use "Download Original" to get the document file</li>
                            <li>Note: This is a viewer - for editing, download and use your preferred editor</li>
                        </ul>
                        <button onclick="loadDocument()" style="margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">🔄 Refresh Document</button>
                    </div>
                </div>
                
                <script>
                    let documentContent = '';
                    let isLoaded = false;
                    
                    // Load document in iframe using document viewer
                    async function loadDocument() {{
                        try {{
                            const documentUrl = '{chosen_url}';
                            const iframe = document.getElementById('documentViewer');
                            
                            // Use Microsoft Office Online viewer for DOCX files
                            if (documentUrl.toLowerCase().includes('.docx')) {{
                                const viewerUrl = `https://view.officeapps.live.com/op/embed.aspx?src=${{encodeURIComponent(documentUrl)}}`;
                                iframe.src = viewerUrl;
                            }}
                            // Use PDF.js viewer for PDF files
                            else if (documentUrl.toLowerCase().includes('.pdf')) {{
                                const viewerUrl = `https://mozilla.github.io/pdf.js/web/viewer.html?file=${{encodeURIComponent(documentUrl)}}`;
                                iframe.src = viewerUrl;
                            }}
                            // Fallback to direct URL
                            else {{
                                iframe.src = documentUrl;
                            }}
                            
                            isLoaded = true;
                        }} catch (error) {{
                            document.getElementById('editor').innerHTML = `
                                <div style="text-align: center; padding: 40px; color: #d32f2f;">
                                    <div style="font-size: 24px; margin-bottom: 10px;">❌</div>
                                    <p>Error loading document: ${{error.message}}</p>
                                </div>
                            `;
                        }}
                    }}
                    
                    function downloadOriginal() {{
                        // Use backend proxy for download
                        const proxyUrl = '{backend}/proxy/docx?url=' + encodeURIComponent('{chosen_url}');
                        const link = document.createElement('a');
                        link.href = proxyUrl;
                        link.download = '{case_id}_original_{sel_ver}.docx';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }}
                    
                    // Note: Save functionality removed since we're now using a document viewer
                    
                    // Load document when page loads
                    window.addEventListener('load', loadDocument);
                </script>
                """
                
                components.html(editor_html, height=750)
                
                # Additional download option for convenience
                st.markdown("### Quick Actions")
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    if st.button("📥 Download DOCX File", key=f"quick_download_{case_id}", type="primary"):
                        try:
                            import requests
                            # Use backend proxy to avoid CORS issues
                            proxy_url = f"{backend}/proxy/docx?url={chosen_url}"
                            response = requests.get(proxy_url, timeout=30)
                            if response.status_code == 200:
                                st.download_button(
                                    "⬇️ Download DOCX",
                                    data=response.content,
                                    file_name=f"{case_id}_ai_report_{sel_ver}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_quick_{case_id}",
                                )
                                st.success("DOCX file ready for download!")
                            else:
                                st.error("Failed to download DOCX file")
                        except Exception as e:
                            st.error(f"Download failed: {str(e)}")
                
                with col2:
                    st.info("💡 **For full editing:**\nDownload the file and open with LibreOffice or Microsoft Word")
            else:
                st.info("No DOCX AI report URL available for the selected version.")

    with tabs[0]:
        st.caption("Record mismatches between Ground Truth and AI by section and subsection. Export as PDF/JSON.")

    # Initialize state bucket per case + selected AI label
    notes_key = f"discrepancy_notes::{case_id}::{(selected_label or 'ai').strip() if 'selected_label' in locals() else 'ai'}"
    if notes_key not in st.session_state:
        st.session_state[notes_key] = []

    # Table of Contents structure
    toc_sections = {
        "1. Overview": [
            "1.1 Executive Summary",
            "1.2 Life Care Planning and Life Care Plans",
            "1.2.1 Life Care Planning",
            "1.2.2 Life Care Plans",
            "1.3 Biography of Medical Expert",
            "1.4 Framework: A Life Care Plan for Ms. Blanca Georgina Ortiz"
        ],
        "2. Summary of Records": [
            "2.1 Summary of Medical Records",
            "2.1.1 Sources",
            "2.1.2 Chronological Synopsis of Medical Records",
            "2.1.3 Diagnostics",
            "2.1.4 Procedure Performed"
        ],
        "3. Interview": [
            "3.1 Recent History",
            "3.1.1 History of Present Injury/Illness",
            "3.2 Subjective History",
            "3.2.1 Current Symptoms",
            "3.2.2 Physical Symptoms",
            "3.2.3 Functional Symptoms",
            "3.3 Review of Systems",
            "3.3.1 Emotional Symptoms",
            "3.3.2 Neurologic",
            "3.3.3 Orthopedic",
            "3.3.4 Cardiovascular",
            "3.3.5 Integumentary",
            "3.3.6 Respiratory",
            "3.3.7 Digestive",
            "3.3.8 Urinary",
            "3.3.9 Circulation",
            "3.3.10 Behavioral",
            "3.4 Past Medical History",
            "3.5 Past Surgical History",
            "3.6 Injections",
            "3.7 Family History",
            "3.8 Allergies",
            "3.9 Drug and Other Allergies",
            "3.10 Medications",
            "3.11 Assistive Device",
            "3.12 Social History",
            "3.13 Education History",
            "3.14 Professional/Work History",
            "3.15 Habits",
            "3.16 Tobacco use",
            "3.17 Alcohol use",
            "3.18 Illicit drugs",
            "3.19 Avocational Activities",
            "3.20 Residential Situation",
            "3.21 Transportation",
            "3.22 Household Responsibilities"
        ],
        "4. Central Opinions": [
            "4.1 Diagnostic Conditions",
            "4.2 Consequent Circumstances",
            "4.2.1 Disabilities",
            "4.2.2 Probable Duration of Care",
            "4.2.3 Average Residual Years",
            "4.2.4 Life Expectancy",
            "4.2.5 Adjustments to Life Expectancy",
            "4.2.6 Probable Duration of Care"
        ],
        "5. Future Medical Requirements": [
            "5.1 Physician Services",
            "5.2 Routine Diagnostics",
            "5.3 Medications",
            "5.4 Laboratory Studies",
            "5.5 Rehabilitation Services",
            "5.6 Equipment & Supplies",
            "5.7 Environmental Modifications & Essential Services",
            "5.8 Acute Care Services"
        ],
        "6. Cost/Vendor Survey": [
            "6.1 Methods, Definitions, and Discussion",
            "6.1.1 Survey Methodology",
            "6.1.2 Definitions and Discussion"
        ],
        "7. Definition & Discussion of Quantitative Methods": [
            "7.1 Definition & Discussion of Quantitative Methods",
            "7.1.1 Nominal Value",
            "7.1.2 Accounting Methods",
            "7.1.3 Variables",
            "7.1.3.1 Independent Variables",
            "7.1.3.2 Dependent Variables",
            "7.1.4 Unit Costs",
            "7.1.5 Counts & Conventions"
        ],
        "8. Probable Duration of Care": [
            "8.1 Probable Duration of Care Metrics"
        ],
        "9. Summary Cost Projection Tables": [
            "Table 1: Routine Medical Evaluation",
            "Table 2: Therapeutic Evaluation",
            "Table 3: Therapeutic Modalities",
            "Table 4: Diagnostic Testing",
            "Table 5: Equipment and Aids",
            "Table 6: Pharmacology",
            "Table 7: Future Aggressive Care/Surgical Intervention",
            "Table 8: Home Care/Home Services",
            "Table 9: Labs"
        ],
        "10. Overview of Medical Expert": []
    }

    # Get section and subsection options
    section_options = list(toc_sections.keys())
    
    ncol1, ncol2 = st.columns([3, 1])
    with ncol1:
        # Create hierarchical options with indentation and arrows
        hierarchical_options = []
        section_to_subsection = {}
        
        for section in section_options:
            subsections = toc_sections.get(section, [])
            if subsections:
                # Add main section
                hierarchical_options.append(section)
                section_to_subsection[section] = section
                
                # Add subsections with indentation and arrows
                for sub in subsections:
                    indented_sub = f"    └─ {sub}"
                    hierarchical_options.append(indented_sub)
                    section_to_subsection[indented_sub] = section
            else:
                # Section without subsections
                hierarchical_options.append(section)
                section_to_subsection[section] = section
        
        section_choice = st.selectbox("Section/Subsection", options=hierarchical_options, index=0)
    with ncol2:
        severity = st.selectbox("Severity", options=["Low", "Medium", "High"], index=1)

    comment = st.text_area("Describe the discrepancy", placeholder="e.g., Missing 'Lisinopril' in medications section compared to ground truth.", key="disc_comment")
    meta_cols = st.columns([0.2, 0.8])
    with meta_cols[0]:
        add_ok = st.button("Add comment", type="primary", key="disc_add_btn")
    with meta_cols[1]:
        st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)

    if 'add_ok' in locals() and add_ok and section_choice and comment:
        # Persist to backend (shared)
        try:
            if requests is not None:
                # Parse hierarchical format
                if section_choice.startswith("    └─ "):
                    # This is a subsection - extract the actual subsection name
                    subsection = section_choice.replace("    └─ ", "")
                    section = section_to_subsection[section_choice]
                else:
                    # This is a main section
                    section = section_choice
                    subsection = section_choice  # Use section as subsection if no subsection
                
                _user = current_user
                payload = {
                    "case_id": case_id,
                    "ai_label": selected_label or None,
                    "section": section,
                    "subsection": subsection,
                    "username": _user,
                    "severity": severity,
                    "comment": comment.strip(),
                }
                requests.post(f"{backend}/comments", json=payload, timeout=8)
        except Exception:
            pass
        st.success("Added.")

    # Load existing comments from backend (shared, user-agnostic)
    notes = st.session_state.get(notes_key, [])

    # Stop here so legacy discrepancy UI below is not rendered outside the tab
    return
    try:
        if requests is not None:
            params = {"ai_label": selected_label} if selected_label else None
            rcm = requests.get(f"{backend}/comments/{case_id}", params=params, timeout=6)
            if rcm.ok:
                server_notes = rcm.json() or []
                # Normalize to our local shape
                _norm = []
                for n in server_notes:
                    sec = n.get("section")
                    subs = n.get("subsection")
                    if not subs:
                        # Default display subsection if missing: first known or section itself
                        opts = toc_sections.get(sec or "", [])
                        subs = (opts[0] if opts else sec)
                    usr = n.get("username") or "anonymous"
                    _norm.append({
                        "id": n.get("id"),
                        "ts": n.get("created_at"),
                        "case_id": n.get("case_id"),
                        "ai_label": n.get("ai_label"),
                        "section": sec,
                        "subsection": subs,
                        "username": usr,
                        "severity": n.get("severity"),
                        "comment": n.get("comment"),
                        "resolved": bool(n.get("resolved") or False),
                    })
                notes = _norm
    except Exception:
        pass

    if notes:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        st.markdown("**Recorded comments**")
        
        # Add CSS to reduce button font size
        st.markdown("""
        <style>
        div[data-testid='stButton'] > button {
            font-size: 0.85rem !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Create a table with inline action buttons
        for n in notes:
            nid = n.get("id")
            if nid:
                is_resolved = bool(n.get("resolved"))
                can_delete = (n.get("username") or "") == (st.session_state.get("username") or st.session_state.get("name") or "")
                
                section = n.get('section','') or '—'
                subsection = n.get('subsection','') or '—'
                combined = f"{section} / {subsection}" if subsection != '—' else section
                when = (n.get("ts", "") or "").replace("T", " ").replace("Z", " UTC")
                comment = n.get('comment','') or ''
                
                # Create a container for each comment row
                with st.container():
                    # Style for resolved comments
                    if is_resolved:
                        st.markdown("<div style='opacity:.85;background:rgba(255,255,255,0.03);padding:.5rem;border-radius:4px;margin:.25rem 0;'>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='padding:.5rem;border-radius:4px;margin:.25rem 0;'>", unsafe_allow_html=True)
                    
                    # Create columns for the comment data and actions
                    col1, col2, col3, col4, col5, col6 = st.columns([1.5, 0.7, 0.6, 1.2, 2, 1])
                    
                    with col1:
                        st.markdown(f"<div style='font-size:0.85rem;'><strong>{combined}</strong></div>" if not is_resolved else f"<div style='font-size:0.85rem;opacity:.7;color:#9aa0a6;'>{combined}</div>", unsafe_allow_html=True)
                    
                    with col2:
                        username = n.get("username") or "—"
                        if is_resolved:
                            st.markdown(f"<div style='font-size:0.85rem;opacity:.7;color:#9aa0a6;'>{username}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='font-size:0.85rem;'>{username}</div>", unsafe_allow_html=True)
                    
                    with col3:
                        severity = n.get("severity","") or "—"
                        if is_resolved:
                            st.markdown(f"<div style='font-size:0.85rem;opacity:.7;color:#9aa0a6;'>{severity}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='font-size:0.85rem;'>{severity}</div>", unsafe_allow_html=True)
                    
                    with col4:
                        if is_resolved:
                            st.markdown(f"<div style='font-size:0.85rem;opacity:.7;color:#9aa0a6;'>{when or '—'}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='font-size:0.85rem;'>{when or '—'}</div>", unsafe_allow_html=True)
                    
                    with col5:
                        if is_resolved:
                            st.markdown(f"<div style='font-size:0.85rem;opacity:.7;color:#9aa0a6;'>{comment}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='font-size:0.85rem;'>{comment}</div>", unsafe_allow_html=True)
                    
                    with col6:
                        # Action buttons
                        btn_col1, btn_col2 = st.columns(2)
                        
                        with btn_col1:
                            label = ("✓ Resolve" if not is_resolved else "✗ Unresolve")
                            if st.button(label, key=f"disc_res_{nid}", use_container_width=True):
                                try:
                                    if requests is not None:
                                        payload = {"id": int(nid), "case_id": case_id, "resolved": (not is_resolved)}
                                        response = requests.patch(f"{backend}/comments/resolve", json=payload, timeout=8)
                                        if response.status_code == 200:
                                            st.success(f"Comment {'resolved' if not is_resolved else 'unresolved'} successfully")
                                            # Clear page cache to show updated state immediately
                                            st.cache_data.clear()
                                        else:
                                            st.error("Failed to update comment status")
                                except Exception as e:
                                    st.error(f"Error updating comment: {str(e)}")
                                st.rerun()
                        
                        with btn_col2:
                            if can_delete:
                                if st.button("🗑️", key=f"disc_del_{nid}", use_container_width=True, help="Delete comment"):
                                    if st.session_state.get(f"confirm_delete_{nid}", False):
                                        try:
                                            if requests is not None:
                                                payload = {"case_id": case_id, "ai_label": selected_label, "ids": [int(nid)]}
                                                response = requests.delete(f"{backend}/comments", json=payload, timeout=8)
                                                if response.status_code == 200:
                                                    st.success("Comment deleted successfully")
                                                    # Clear page cache to show updated state immediately
                                                    st.cache_data.clear()
                                                    # Reset confirmation state
                                                    if f"confirm_delete_{nid}" in st.session_state:
                                                        del st.session_state[f"confirm_delete_{nid}"]
                                                else:
                                                    st.error("Failed to delete comment")
                                        except Exception as e:
                                            st.error(f"Error deleting comment: {str(e)}")
                                    else:
                                        st.session_state[f"confirm_delete_{nid}"] = True
                                        st.warning("Click 🗑️ again to confirm")
                                    st.rerun()
                            else:
                                st.markdown("")  # Empty space for non-deletable comments
                    
                    st.markdown("</div>", unsafe_allow_html=True)

        # (Inline delete buttons are in each row above)

        # Exporters
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        exp1, exp2, exp3 = st.columns([0.35, 0.35, 0.3])
        # JSON export (includes current comments loaded)
        import json, io as _io
        json_bytes = _io.BytesIO(json.dumps({
            "case_id": case_id,
            "ai_label": selected_label or "—",
            "patient": patient or "—",
            "notes": notes,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }, ensure_ascii=False, indent=2).encode("utf-8"))
        with exp1:
            st.download_button(
                label="⬇️ Download JSON",
                data=json_bytes.getvalue(),
                file_name=f"{case_id}_discrepancies.json",
                mime="application/json",
                use_container_width=True,
                key="disc_json_dl",
            )

        # PDF export (try reportlab; fallback to HTML)
        pdf_data = None
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            buf = _io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Discrepancies {case_id}")
            styles = getSampleStyleSheet()
            story = []
            title = f"Case {case_id} — Discrepancy Report"
            story.append(Paragraph(title, styles['Title']))
            sub = f"Patient: {patient or '—'} | AI: {selected_label or '—'} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            story.append(Paragraph(sub, styles['Normal']))
            story.append(Spacer(1, 12))
            table_data = [["Section", "Subsection", "Severity", "Comment"]]
            for n in notes:
                table_data.append([
                    n.get("section",""),
                    n.get("subsection",""),
                    n.get("severity",""),
                    n.get("comment",""),
                ])
            tbl = Table(table_data, colWidths=[120, 120, 60, 220])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
            ]))
            story.append(tbl)
            doc.build(story)
            pdf_data = buf.getvalue()
        except Exception:
            pdf_data = None

        with exp2:
            if pdf_data:
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_data,
                    file_name=f"{case_id}_discrepancies.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="disc_pdf_dl",
                )
            else:
                # HTML fallback
                html_lines = [
                    f"<h2>Case {case_id} — Discrepancy Report</h2>",
                    f"<div>Patient: {patient or '—'} | AI: {selected_label or '—'} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>",
                    "<table border='1' cellspacing='0' cellpadding='6' style='border-collapse:collapse;margin-top:6px;'>",
                    "<tr><th>Section</th><th>Subsection</th><th>Severity</th><th>Comment</th></tr>",
                ]
                for n in notes:
                    html_lines.append(
                        f"<tr><td>{n.get('section','')}</td><td>{n.get('subsection','')}</td><td>{n.get('severity','')}</td><td>{n.get('comment','')}</td></tr>"
                    )
                html_lines.append("</table>")
                html_bytes = "\n".join(html_lines).encode("utf-8")
                st.download_button(
                    label="⬇️ Download HTML (PDF fallback)",
                    data=html_bytes,
                    file_name=f"{case_id}_discrepancies.html",
                    mime="text/html",
                    use_container_width=True,
                    key="disc_html_dl",
                )

        with exp3:
            # Clear all
            if st.button("Clear all", key="disc_clear_all"):
                st.session_state[notes_key] = []
                st.rerun()

if __name__ == "__main__":
    main()


