import streamlit as st
import os
import streamlit.components.v1 as components
from urllib.parse import quote
from app.ui import inject_base_styles, theme_provider, top_nav
import time


def ensure_authenticated() -> bool:
    if st.session_state.get("authentication_status") is True:
        return True
    st.warning("Please login to access this page.")
    st.stop()


def _get_backend_base() -> str:
    params = st.query_params if hasattr(st, "query_params") else {}
    return (
        (params.get("api", [None])[0] if isinstance(params.get("api"), list) else params.get("api"))
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
    ).rstrip("/")


def _extract_patient_from_strings(case_id: str, *, gt_key: str | None = None, ai_label: str | None = None, doc_label: str | None = None) -> str | None:
    """Best-effort extraction of a patient name from common S3 key patterns.

    Handles variations like:
    - <case>_LCP_First Last_rest.ext
    - <case>-LCP-First-Last_rest.ext
    - <case>_First_Last_rest.ext
    - Path prefixes (e.g., bucket/1234/GroundTruth/<file>)
    """
    try:
        import re, os
        import urllib.parse
        if not gt_key:
            return None
        decoded_key = urllib.parse.unquote(gt_key)
        filename = os.path.basename(decoded_key)

        patterns = [
            rf"^{case_id}[-_]+LCP[-_]+([^-_.]+(?:[\s_-][^-_.]+)*)",  # with LCP marker
            rf"^{case_id}[-_]+([^-_.]+(?:[\s_-][^-_.]+)*)",            # without LCP
        ]

        for pat in patterns:
            m = re.search(pat, filename, flags=re.IGNORECASE)
            if m:
                raw = m.group(1).strip()
                # Normalize separators to spaces and collapse repeats
                norm = re.sub(r"[_-]+", " ", raw)
                norm = re.sub(r"\s+", " ", norm).strip()
                # Keep at most first and last two tokens to avoid trailing garbage
                tokens = [t for t in norm.split(" ") if t]
                if len(tokens) >= 1:
                    # Heuristic: take first two tokens as "First Last" when available
                    take = tokens[:2] if len(tokens) > 1 else tokens
                    return " ".join(take)
        return None
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=600)  # Cache for 10 minutes
def _case_to_patient_map(backend: str, cases: list[str]) -> dict[str, str]:
    """Build a mapping of case_id -> patient name (only from Ground Truth)."""
    try:
        import requests
        import urllib.parse
        from concurrent.futures import ThreadPoolExecutor, as_completed
    except Exception:
        return {}
    
    def _fetch_patient_for_case(cid: str) -> tuple[str, str | None]:
        """Fetch patient name for a single case."""
        try:
            r2 = requests.get(f"{backend}/s3/{cid}/latest/assets", timeout=4)
            if r2.ok:
                assets = r2.json() or {}
                gt_url = assets.get("ground_truth")
                if gt_url:
                    parsed = urllib.parse.urlparse(gt_url)
                    gt_key = parsed.path.lstrip('/')
                    bucket_name = parsed.netloc.split('.')[0]
                    if gt_key.startswith(f'{bucket_name}/'):
                        gt_key = gt_key[len(bucket_name)+1:]
                    name = _extract_patient_from_strings(cid, gt_key=gt_key)
                    return cid, name
        except Exception:
            pass
        return cid, None
    
    out: dict[str, str] = {}
    # Use ThreadPoolExecutor for parallel requests
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_case = {executor.submit(_fetch_patient_for_case, cid): cid for cid in cases}
        for future in as_completed(future_to_case):
            cid, name = future.result()
            if name:
                out[cid] = name
    return out


@st.cache_data(show_spinner=False, ttl=180)  # Cache for 3 minutes
def _get_all_cases(backend: str) -> list[str]:
    """Fetch all case IDs from S3 with caching."""
    try:
        import requests
        r = requests.get(f"{backend}/s3/cases", timeout=10)
        if r.ok:
            data = r.json() or {}
            return data.get("cases", []) or []
    except Exception:
        pass
    return []


@st.cache_data(show_spinner=False, ttl=300)  # Cache for 5 minutes
def _get_case_outputs(backend: str, case_id: str) -> list[dict]:
    """Fetch outputs for a specific case with caching."""
    try:
        import requests
        r = requests.get(f"{backend}/s3/{case_id}/outputs", timeout=8)
        if r.ok:
            data = r.json() or {}
            items = data.get("items", []) or []
            return items
        else:
            return []
    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=120)  # Cache for 2 minutes
def _get_case_assets(backend: str, case_id: str) -> dict:
    """Fetch assets for a specific case with caching."""
    try:
        import requests
        r = requests.get(f"{backend}/s3/{case_id}/latest/assets", timeout=10)
        if r.ok:
            return r.json() or {}
    except Exception:
        pass
    return {}


@st.cache_data(show_spinner=False, ttl=60)  # Cache for 1 minute
def _get_case_comments(backend: str, case_id: str, ai_label: str = None) -> list[dict]:
    """Fetch comments for a specific case with caching."""
    try:
        import requests
        params = {"ai_label": ai_label} if ai_label else None
        r = requests.get(f"{backend}/comments/{case_id}", params=params, timeout=8)
        if r.ok:
            return r.json() or []
    except Exception:
        pass
    return []


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def main() -> None:
    st.set_page_config(page_title="History (All Cases)", page_icon="🗂️", layout="wide")
    theme_provider()
    inject_base_styles()
    # Page-scoped compact buttons and responsive table
    st.markdown(
        """
        <style>
        .stButton > button { font-size: 0.85rem; padding: .25rem .55rem; }
        @media (max-width: 1100px) { .stButton > button { font-size: 0.80rem; padding: .2rem .5rem; } }
        @media (max-width: 900px) { .stButton > button { font-size: 0.78rem; padding: .18rem .45rem; } }
        
        /* Responsive table adjustments */
        @media (max-width: 1200px) {
            .history-table { grid-template-columns: 180px 120px 110px 1fr 1fr 1fr !important; }
        }
        @media (max-width: 1000px) {
            .history-table { grid-template-columns: 160px 100px 90px 1fr 1fr 1fr !important; }
        }
        @media (max-width: 800px) {
            .history-table { grid-template-columns: 140px 80px 80px 1fr 1fr 1fr !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    ensure_authenticated()

    # Nav bar
    top_nav(active="History")

    try:
        import requests
    except Exception:
        st.error("Requests not available.")
        return

    backend = _get_backend_base()

    st.markdown("## History: Browse All Cases")
    st.caption("Browse all cases directly from S3 regardless of saved history.")

    # Fetch all case ids from S3 (cached)
    cases = _get_all_cases(backend)
    if not cases:
        st.markdown(
            """
            <div style="text-align: center; padding: 3rem 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; margin: 2rem 0;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">📚</div>
                <h2 style="color: white; margin-bottom: 1rem; font-weight: 600;">No Cases Found</h2>
                <p style="color: rgba(255,255,255,0.9); font-size: 1.1rem; margin-bottom: 2rem; max-width: 500px; margin-left: auto; margin-right: auto;">
                    Please generate a case report first to view your case history and analysis.
                </p>
                <div style="margin-top: 2rem;">
                    <a href="?case_id=0000&start=0" style="background: rgba(255,255,255,0.2); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; border: 1px solid rgba(255,255,255,0.3); display: inline-block;">
                        Go to Case Report →
                    </a>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    # Build patient map (best-effort, cached) - only for first 20 cases for speed
    with st.spinner("Loading patient names…"):
        cases_to_load = cases[:20]  # Limit to first 20 cases for speed
        cid_to_patient = _case_to_patient_map(backend, cases_to_load)

    # Build display labels and predictive select - only for visible cases
    def _label_for(cid: str) -> str:
        p = cid_to_patient.get(cid)
        return f"{cid} — {p}" if p else cid

    # Only build labels for first 50 cases for speed
    visible_cases = cases[:50]
    display_labels = [_label_for(cid) for cid in visible_cases]
    label_to_cid = {lbl: cid for lbl, cid in zip(display_labels, visible_cases)}

    st.markdown("<div style='height:.25rem'></div>", unsafe_allow_html=True)
    
    # Single list that shows all cases on click; built-in typeahead filters as you type
    sel_label = st.selectbox(
        "Search or select case (type case ID or patient name)",
        options=sorted(display_labels, key=lambda s: s.lower()),
        index=None,  # do not preselect; wait for user action
        placeholder="Start typing to filter, then pick a case",
        key="history_case_select_unified",
    )

    # Handle selectbox selection
    if not sel_label:
        st.info("Select a case to continue.")
        return

    # Extract case_id from selected label
    if sel_label in label_to_cid:
        case_id = label_to_cid[sel_label]
    else:
        # If not in label_to_cid, try to extract from the label itself
        if "—" in sel_label:
            case_id = sel_label.split("—", 1)[0].strip()
        else:
            case_id = sel_label.strip()
    patient = sel_label.split("—", 1)[1].strip() if "—" in sel_label else cid_to_patient.get(case_id)

    # Patient badge + compact header
    if patient:
        initials = _initials(patient)
        st.markdown(
            f"""
            <div style='display:flex;align-items:center;gap:.5rem;margin:.25rem 0 .5rem;'>
              <div style='width:34px;height:34px;border-radius:50%;background:rgba(99,102,241,0.25);display:flex;align-items:center;justify-content:center;font-weight:700;'>{initials}</div>
              <div style='font-weight:600'>{patient}</div>
              <div style='opacity:.8'>|</div>
              <div style='opacity:.9'>Case {case_id}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Fetch outputs (AI+Doctor) list under Output/ (cached) - only when case is selected
    if case_id:
        with st.spinner("Loading case data…"):
            outputs = _get_case_outputs(backend, case_id)
            # Fetch ground truth assets (cached)
            assets = _get_case_assets(backend, case_id)
    else:
        outputs = []
        assets = {}
    
    gt_pdf = assets.get("ground_truth_pdf")
    gt_generic = assets.get("ground_truth")
    gt_effective_pdf_url = None

    # --- Results Table (from Results page) ---
    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    st.markdown("### Report Summary")
    st.caption("Overview of all reports for this case")
    
    # Helper functions for table (from Results page)
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

    # Code version fetching - prioritize stored version over GitHub
    @st.cache_data(ttl=300)
    def _fetch_code_version_for_case(case_id: str) -> str:
        try:
            import requests as _rq
            import json as _json, base64 as _b64
            
            # First try to get stored version from backend
            try:
                backend_url = st.session_state.get("backend_url", "http://localhost:8000")
                backend_r = _rq.get(f"{backend_url}/reports/{case_id}/code-version", timeout=5)
                if backend_r.ok:
                    backend_data = backend_r.json()
                    stored_version = backend_data.get("code_version")
                    if stored_version and stored_version != "Unknown" and stored_version != "—":
                        return stored_version
            except Exception as e:
                pass
            
            # Only fetch from GitHub if we have a webhook response (new report)
            webhook_text = st.session_state.get("last_webhook_text")
            if not webhook_text:
                # Check session state as fallback
                sess_ver = (st.session_state.get("code_version_by_case") or {}).get(str(case_id)) or st.session_state.get("code_version")
                return sess_ver if sess_ver else "—"
            
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

    # Build table data
    try:
        with st.spinner("Loading report summary…"):
            from datetime import datetime
            code_version = _fetch_code_version_for_case(case_id)
            generated_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        
        # Determine ground truth URL for table
        if gt_pdf:
            gt_effective_pdf_url = gt_pdf
        elif gt_generic:
            # Try to convert to PDF
            raw_key = assets.get("ground_truth_key") if isinstance(assets, dict) else None
            params = {"key": raw_key} if raw_key else {"url": gt_generic}
            try:
                import requests as _rq
                r2 = _rq.get(f"{backend}/s3/ensure-pdf", params=params, timeout=10)
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

        rows: list[tuple[str, str, str, str | None, str | None, str | None, str, str, str, str, str]] = []
        if outputs:
            for o in outputs:
                doc_version = extract_version(o.get("label"))
                # Use timestamp from S3 metadata instead of fake timestamp
                report_timestamp = o.get("timestamp") or generated_ts
                ocr_start, ocr_end, total_tokens, input_tokens, output_tokens = extract_metadata(o)
                rows.append((report_timestamp, code_version, doc_version, gt_effective_pdf_url, o.get("ai_url"), o.get("doctor_url"), ocr_start, ocr_end, total_tokens, input_tokens, output_tokens))
        else:
            rows.append((generated_ts, code_version, "—", gt_effective_pdf_url, None, None, "—", "—", "—", "—", "—"))

        # Add CSS for horizontal scrolling
        st.markdown("""
        <style>
        .table-container {
            overflow-x: auto;
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 8px;
            margin-top: 12px;
        }
        
        .history-table {
            min-width: 2400px;
            display: grid;
            gap: 0;
            grid-template-columns: 220px 160px 140px 3.6fr 3.6fr 3.6fr 120px 120px 140px 140px 140px;
        }
        
        /* Add visual separation between Ground Truth and AI Generated columns */
        .history-table > div:nth-child(4) {
            border-right: 2px solid rgba(255,255,255,0.25) !important;
        }
        
        /* Add vertical borders to table cells */
        .history-table > div {
            border-right: 1px solid rgba(255,255,255,0.12);
        }
        
        /* Remove right border from last column */
        .history-table > div:nth-child(11n) {
            border-right: none;
        }
        </style>
        """, unsafe_allow_html=True)

        # Render table HTML
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
            '</div>'
        ]
        for (gen_time, code_ver, doc_ver, gt_url, ai_url, doc_url, ocr_start, ocr_end, total_tokens, input_tokens, output_tokens) in rows:
            gt_dl = dl_link(gt_url)
            ai_dl = dl_link(ai_url)
            doc_dl = dl_link(doc_url)
            gt_link = f'<a href="{gt_dl}" class="st-a" download>{file_name(gt_url)}</a>' if gt_dl else '<span style="opacity:.6;">—</span>'
            ai_link = f'<a href="{ai_dl}" class="st-a" download>{file_name(ai_url)}</a>' if ai_dl else '<span style="opacity:.6;">—</span>'
            doc_link = f'<a href="{doc_dl}" class="st-a" download>{file_name(doc_url)}</a>' if doc_dl else '<span style="opacity:.6;">—</span>'
            
            # Append each row element individually
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
            table_html.append('</div>')
        table_html.append('</div>')
        st.markdown("".join(table_html), unsafe_allow_html=True)
        
        # Extra breathing room below the summary table
        st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading report summary: {str(e)}")
        st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)

    # Denser layout height
    iframe_h = 480

    col1, col2, col3 = st.columns(3)

    # Ground Truth
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

    # AI selector (dropdown) - optimized to prevent reloads
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
        
        # Initialize session state for AI selection
        ai_key = f"history_ai_label_{case_id}"
        if ai_key not in st.session_state:
            st.session_state[ai_key] = None
            
        labels = [o.get("label") or (o.get("ai_key") or "").split("/")[-1] for o in outputs]
        
        # Use session state to maintain selection across reruns
        if labels:
            # Find current selection index
            current_label = st.session_state.get(ai_key)
            if current_label and current_label in labels:
                default_index = labels.index(current_label)
            else:
                default_index = 0
                st.session_state[ai_key] = labels[0]
            
            selected_label = st.selectbox(
                "Select AI output", 
                options=labels, 
                index=default_index, 
                key=f"ai_dropdown_{case_id}",
                on_change=lambda: st.session_state.update({ai_key: st.session_state[f"ai_dropdown_{case_id}"]})
            )
            st.session_state[ai_key] = selected_label
        else:
            selected_label = None
            
        sel_ai = None
        if selected_label:
            sel_ai = next((o for o in outputs if (o.get("label") or (o.get("ai_key") or "").split("/")[-1]) == selected_label), None)
        ai_effective_pdf_url = None
        if sel_ai and sel_ai.get("ai_url"):
            st.markdown(f"<iframe src=\"{sel_ai['ai_url']}\" width=\"100%\" height=\"{iframe_h}\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
            ai_effective_pdf_url = sel_ai["ai_url"]
        else:
            st.info("Not available")

    # Doctor viewer
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

    # Sync viewer with lock/unlock
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    enable_sync = st.checkbox("Enable synchronized scrolling (Ground Truth ↔ AI Generated)", value=False, key="history_sync")
    if enable_sync and gt_effective_pdf_url and ai_effective_pdf_url:
        st.markdown("<div style='text-align:center;margin-bottom:0.5rem;'><small>💡 <strong>Tip:</strong> Scroll to align pages first, then use the lock button in the viewer</small></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align:center;margin-bottom:0.5rem;'><small>🔓 <strong>Unlocked:</strong> Scroll independently • 🔒 <strong>Locked:</strong> Scroll together</small></div>", unsafe_allow_html=True)
        sync_height = 600
        html = """
        <div style=\"position:relative;\">
          <div style=\"display:grid;grid-template-columns:1fr 1fr;gap:12px;\">
            <div id=\"leftPane\" style=\"height:__H__px;overflow:auto;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:6px;\"></div>
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
            const delta = a.scrollTop - (a.lastScrollTop || 0);
            a.lastScrollTop = a.scrollTop;
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
          const lockButton = document.getElementById('lockButton');
          lockButton.addEventListener('click', () => {
            if (scrollLocked) unlockScroll(); else lockScroll();
          });
          updateLockButton();
          linkScroll(left, right);
          linkScroll(right, left);
          window.addEventListener('resize', () => {
            renderPdf('__GT__', 'leftPane');
            renderPdf('__AI__', 'rightPane');
          });
        })();
        </script>
        """
        html = html.replace("__H__", str(sync_height))
        proxy_gt = f"{backend}/proxy/pdf?url=" + quote(gt_effective_pdf_url, safe="")
        proxy_ai = f"{backend}/proxy/pdf?url=" + quote(ai_effective_pdf_url, safe="")
        html = html.replace("""__GT__""", proxy_gt).replace("""__AI__""", proxy_ai)
        components.html(html, height=sync_height + 16)


    # --- Discrepancy notes ---
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown("### Discrepancy Notes")
    st.caption("Record mismatches between Ground Truth and AI by section and subsection.")

    # Resolve current user
    current_user = (
        st.session_state.get("username")
        or st.session_state.get("name")
        or st.session_state.get("user")
        or st.session_state.get("user_email")
        or "anonymous"
    )
    if st.session_state.get("username") is None and current_user:
        st.session_state["username"] = current_user

    # Table of Contents (same as Results)
    toc_sections = {
        "1. Overview": [
            "1.1 Executive Summary",
            "1.2 Life Care Planning and Life Care Plans",
            "1.2.1 Life Care Planning",
            "1.2.2 Life Care Plans",
            "1.3 Biography of Medical Expert",
            "1.4 Framework: A Life Care Plan for Ms. Blanca Georgina Ortiz",
        ],
        "2. Summary of Records": [
            "2.1 Summary of Medical Records",
            "2.1.1 Sources",
            "2.1.2 Chronological Synopsis of Medical Records",
            "2.1.3 Diagnostics",
            "2.1.4 Procedure Performed",
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
            "3.22 Household Responsibilities",
        ],
        "4. Central Opinions": [
            "4.1 Diagnostic Conditions",
            "4.2 Consequent Circumstances",
            "4.2.1 Disabilities",
            "4.2.2 Probable Duration of Care",
            "4.2.3 Average Residual Years",
            "4.2.4 Life Expectancy",
            "4.2.5 Adjustments to Life Expectancy",
            "4.2.6 Probable Duration of Care",
        ],
        "5. Future Medical Requirements": [
            "5.1 Physician Services",
            "5.2 Routine Diagnostics",
            "5.3 Medications",
            "5.4 Laboratory Studies",
            "5.5 Rehabilitation Services",
            "5.6 Equipment & Supplies",
            "5.7 Environmental Modifications & Essential Services",
            "5.8 Acute Care Services",
        ],
        "6. Cost/Vendor Survey": [
            "6.1 Methods, Definitions, and Discussion",
            "6.1.1 Survey Methodology",
            "6.1.2 Definitions and Discussion",
        ],
        "7. Definition & Discussion of Quantitative Methods": [
            "7.1 Definition & Discussion of Quantitative Methods",
            "7.1.1 Nominal Value",
            "7.1.2 Accounting Methods",
            "7.1.3 Variables",
            "7.1.3.1 Independent Variables",
            "7.1.3.2 Dependent Variables",
            "7.1.4 Unit Costs",
            "7.1.5 Counts & Conventions",
        ],
        "8. Probable Duration of Care": ["8.1 Probable Duration of Care Metrics"],
        "9. Summary Cost Projection Tables": [
            "Table 1: Routine Medical Evaluation",
            "Table 2: Therapeutic Evaluation",
            "Table 3: Therapeutic Modalities",
            "Table 4: Diagnostic Testing",
            "Table 5: Equipment and Aids",
            "Table 6: Pharmacology",
            "Table 7: Future Aggressive Care/Surgical Intervention",
            "Table 8: Home Care/Home Services",
            "Table 9: Labs",
        ],
        "10. Overview of Medical Expert": [],
    }

    # Input UI
    section_options = list(toc_sections.keys())
    n1, n2 = st.columns([3, 1])
    with n1:
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
        
        section_choice = st.selectbox("Section/Subsection", options=hierarchical_options, index=0, key="history_disc_sec")
    with n2:
        severity = st.selectbox("Severity", options=["Low", "Medium", "High"], index=1, key="history_disc_sev")

    comment_text = st.text_area("Describe the discrepancy", key="history_disc_text")
    add_ok = st.button("Add comment", type="primary", key="history_add_btn")

    # Backend base
    backend = _get_backend_base()

    if add_ok and section_choice and comment_text:
        try:
            import requests as _rq
            # Parse hierarchical format
            if section_choice.startswith("    └─ "):
                # This is a subsection - extract the actual subsection name
                subsection = section_choice.replace("    └─ ", "")
                section = section_to_subsection[section_choice]
            else:
                # This is a main section
                section = section_choice
                subsection = section_choice  # Use section as subsection if no subsection
            
            payload = {
                "case_id": case_id,
                "ai_label": selected_label or None,
                "section": section,
                "subsection": subsection,
                "username": current_user,
                "severity": severity,
                "comment": comment_text.strip(),
            }
            _rq.post(f"{backend}/comments", json=payload, timeout=8)
            # Clear cache for comments to show new comment immediately
            _get_case_comments.clear()
            st.success("Added.")
        except Exception:
            st.warning("Failed to add comment.")

    # List comments (cached)
    notes = _get_case_comments(backend, case_id, selected_label)

    if notes:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        st.markdown("**Recorded comments**")
        
        # Create HTML table for perfect alignment
        table_html = [
            '<div style="border:1px solid rgba(255,255,255,0.12);border-radius:8px;overflow:hidden;margin-top:8px;">',
            '<div style="display:grid;grid-template-columns:2fr 0.7fr 0.6fr 2fr 1.2fr;gap:0;border-bottom:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);">',
            '<div style="padding:.5rem .75rem;font-weight:700;">Section/Subsection</div>',
            '<div style="padding:.5rem .75rem;font-weight:700;">User</div>',
            '<div style="padding:.5rem .75rem;font-weight:700;">Severity</div>',
            '<div style="padding:.5rem .75rem;font-weight:700;">When</div>',
            '<div style="padding:.5rem .75rem;font-weight:700;">Actions</div>',
            '</div>'
        ]
        
        # Add data rows
        for n in notes:
            is_resolved = bool(n.get("resolved"))
            row_style = "opacity:.85;background:rgba(255,255,255,0.03);" if is_resolved else ""
            text_style = "opacity:.7;color:#9aa0a6;" if is_resolved else ""
            
            section = n.get('section') or '—'
            subsection = n.get("subsection") or (toc_sections.get(n.get("section") or "", [])[:1] or [n.get("section")])[0]
            combined = f"{section} / {subsection}" if subsection and subsection != '—' else section
            when = (n.get("created_at") or "").replace("T", " ").replace("Z", " UTC")
            comment = n.get('comment') or ''
            
            table_html.append(f'<div style="display:grid;grid-template-columns:2fr 0.7fr 0.6fr 2fr 1.2fr;gap:0;border-bottom:1px solid rgba(255,255,255,0.06);{row_style}">')
            table_html.append(f'<div style="padding:.5rem .75rem;{text_style}">{combined}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;{text_style}">{n.get("username") or "anonymous"}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;{text_style}">{n.get("severity") or "—"}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;{text_style}">{when or "—"}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;{text_style}">{comment}</div>')
            table_html.append('</div>')
        
        table_html.append('</div>')
        st.markdown("".join(table_html), unsafe_allow_html=True)
        
        # Add action buttons below the table
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        for n in notes:
            nid = n.get("id")
            if nid:
                is_resolved = bool(n.get("resolved"))
                can_delete = (n.get("username") or "") == (st.session_state.get("username") or st.session_state.get("name") or "")
                
                col1, col2, col3 = st.columns([0.3, 0.3, 0.4])
                with col1:
                    label = ("Resolve\u00A0\u00A0\u00A0\u00A0" if not is_resolved else "Unresolve\u00A0\u00A0\u00A0")
                    if st.button(label, key=f"history_disc_res_{nid}"):
                        try:
                            _rq.patch(f"{backend}/comments/resolve", json={"id": int(nid), "case_id": case_id, "resolved": (not is_resolved)}, timeout=8)
                            # Clear cache for comments to show updated state immediately
                            _get_case_comments.clear()
                        except Exception:
                            pass
                        st.rerun()
                with col2:
                    if can_delete and st.button("Delete\u00A0", key=f"history_disc_del_{nid}"):
                        try:
                            _rq.delete(f"{backend}/comments", json={"case_id": case_id, "ai_label": selected_label, "ids": [int(nid)]}, timeout=8)
                            # Clear cache for comments to show updated state immediately
                            _get_case_comments.clear()
                        except Exception:
                            pass
                        st.rerun()
                with col3:
                    st.markdown("")  # Empty space

if __name__ == "__main__":
    main()