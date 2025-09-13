import streamlit as st
import os
import streamlit.components.v1 as components
from urllib.parse import quote
from app.ui import inject_base_styles, theme_provider, top_nav
import time


def ensure_authenticated() -> bool:
    # Check if user is authenticated
    auth_status = st.session_state.get("authentication_status")
    
    if auth_status is True:
        return True
    elif auth_status is False:
        st.error("❌ Invalid username or password. Please login again.")
        st.stop()
    else:  # auth_status is None
        st.warning("🔐 Please login to access this page.")
        
        # Add login button to redirect
        if st.button("Go to Login Page", type="primary"):
            st.switch_page("main.py")
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
        r = requests.get(f"{backend}/s3/{case_id}/outputs", timeout=20)
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


@st.cache_data(show_spinner=False, ttl=120)
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


def _probe_metrics_from_outputs(backend: str, case_id: str, outputs: list[dict]) -> None:
    """Scan output file names for 12-digit timestamps and warm backend metrics cache.
    This helps populate OCR/tokens when the JSON exists in S3.
    """
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

    # Build labels for all cases so users can select any case (avoid blank table due to slicing)
    visible_cases = cases
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
            # Exclude legacy Edited subfolder entries from display
            try:
                outputs = [o for o in outputs if not (
                    (o.get("ai_key") or "").lower().find("/output/edited/") >= 0 or
                    (o.get("doctor_key") or "").lower().find("/output/edited/") >= 0
                )]
            except Exception:
                pass
            # Fetch ground truth assets (cached)
            assets = _get_case_assets(backend, case_id)
            # Warm metrics cache based on outputs so summary fills in
            _probe_metrics_from_outputs(backend, case_id, outputs)
    else:
        outputs = []
        assets = {}
    
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
            outputs = [o for o in outputs if canon_re.match(_base_name(o) or "")]
        except Exception:
            pass
    
    # Debug panel removed for production cleanliness
    
    # Augment from DB when no S3 outputs exist (helps for mock cases like 9999)
    if not outputs:
        try:
            import requests as _rq
            backend_url = _get_backend_base()
            r = _rq.get(f"{backend_url}/runs/{case_id}", timeout=5)
            if r.ok:
                p = r.json() or {}
                run = (p.get("run") if isinstance(p, dict) else None) or {}
                if run:
                    outputs = [
                        {
                            "label": run.get("document_version") or "—",
                            "timestamp": run.get("created_at"),
                            "gt_url": run.get("pdf_url"),
                            "ai_url": run.get("ai_url"),
                            "doctor_url": run.get("doc_url"),
                            "ocr_start_time": run.get("ocr_start_time"),
                            "ocr_end_time": run.get("ocr_end_time"),
                            "total_tokens_used": run.get("total_tokens_used"),
                            "total_input_tokens": run.get("total_input_tokens"),
                            "total_output_tokens": run.get("total_output_tokens"),
                        }
                    ]
        except Exception:
            pass
    
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

    # Code version fetching - backend, then GitHub state file by default
    @st.cache_data(ttl=300)
    def _fetch_code_version_for_case(case_id: str) -> str:
        try:
            import requests as _rq
            import json as _json, base64 as _b64, os as _os
            backend_url = _get_backend_base()
            
            # 1) Try stored version from backend
            try:
                backend_r = _rq.get(f"{backend_url}/reports/{case_id}/code-version", timeout=5)
                if backend_r.ok:
                    backend_data = backend_r.json() or {}
                    stored_version = backend_data.get("code_version")
                    if stored_version and stored_version not in ("Unknown", "—"):
                        return stored_version
            except Exception:
                pass
            
            # 2) Session-state fallback
                sess_ver = (st.session_state.get("code_version_by_case") or {}).get(str(case_id)) or st.session_state.get("code_version")
            if sess_ver and sess_ver not in ("Unknown", "—"):
                return sess_ver
            
            # 3) Fetch GitHub state file
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
                        _rq.post(f"{backend_url}/reports/{case_id}/code-version", json={"code_version": code_ver}, timeout=5)
                            except Exception:
                                pass
                    return code_ver
                    return "—"
        except Exception:
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
            st.warning("No outputs returned for this case. Verify the backend `/s3/{case_id}/outputs` endpoint and try Refetch/Cache Clear in Debug.")
            rows.append((generated_ts, code_version, "—", gt_effective_pdf_url, None, None, "—", "—", "—", "—", "—"))

        # Pagination controls for summary table (10 per page)
        sum_page_size = 10
        sum_total = len(rows)
        sum_total_pages = max(1, (sum_total + sum_page_size - 1) // sum_page_size)
        sum_pg_key = f"hist_summary_page_{case_id}"
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
            min-width: 3200px;
            display: grid;
            gap: 0;
            grid-template-columns: 240px 180px 200px 3.6fr 3.6fr 3.6fr 140px 140px 160px 160px 160px 180px 180px 180px 180px;
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
        .history-table > div:nth-child(15n) {
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
            '<div style="padding:.75rem 1rem;font-weight:700;">Section 2 Time</div>',
            '<div style="padding:.75rem 1rem;font-weight:700;">Section 3 Time</div>',
            '<div style="padding:.75rem 1rem;font-weight:700;">Section 4 Time</div>',
            '<div style="padding:.75rem 1rem;font-weight:700;">Section 9 Time</div>',
            '</div>'
        ]
        for (gen_time, code_ver, doc_ver, gt_url, ai_url, doc_url, ocr_start, ocr_end, total_tokens, input_tokens, output_tokens) in page_rows:
            # If metrics are blank, try S3 JSON lookup; prefer direct version if doc_ver looks like timestamp
            if (ocr_start == '—' and ocr_end == '—' and total_tokens == '—'):
                met = None
                # Direct probe when doc_ver is a 12-digit timestamp
                try:
                    import re as _re
                    if _re.match(r"^\d{12}$", str(doc_ver or "")):
                        met = _get_metrics_for_version(backend, case_id, f"{case_id}-{doc_ver}")
                except Exception:
                    met = None
                # Fallback: infer from label/ai_key in outputs
                try:
                    # Find source item in outputs to get label/ai_key
                    src = next((it for it in outputs if (it.get('ai_url') == ai_url) or (it.get('label') or '') == doc_ver or (it.get('ai_key') or '').endswith(doc_ver)), None)
                except Exception:
                    src = None
                if not met:
                    versions = _infer_versions_from_label(case_id, (src or {}).get('label'), (src or {}).get('ai_key'))
                    for v in versions:
                        met = _get_metrics_for_version(backend, case_id, v)
                        if met:
                            break
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
                    sec2dur = sec3dur = sec4dur = sec9dur = '—'
            else:
                sec2dur = sec3dur = sec4dur = sec9dur = '—'
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
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec2dur}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec3dur}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec4dur}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;font-size:0.85rem;">{sec9dur}</div>')
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
            
        # Only show PDF AI outputs in dropdown (DOCX handled in editor below)
        from urllib.parse import urlparse
        def _is_pdf(u: str | None) -> bool:
            if not isinstance(u, str) or not u:
                return False
            try:
                return urlparse(u).path.lower().endswith('.pdf')
            except Exception:
                return u.lower().endswith('.pdf')
        _pdf_outputs = [o for o in outputs if _is_pdf(o.get("ai_url"))]
        # Fallback: some pipelines attach PDF on doctor_url or rename; include those
        if not _pdf_outputs:
            _pdf_outputs = [o for o in outputs if _is_pdf(o.get("ai_url")) or _is_pdf(o.get("doctor_url"))]
        # Final fallback: if still empty, show original outputs to avoid a blank dropdown
        if not _pdf_outputs:
            _pdf_outputs = outputs
        labels = [o.get("label") or (o.get("ai_key") or "").split("/")[-1] for o in _pdf_outputs]
        
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
            sel_ai = next((o for o in _pdf_outputs if (o.get("label") or (o.get("ai_key") or "").split("/")[-1]) == selected_label), None)
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


    # --- Discrepancy: tabbed UI (Comments | AI Report Editor) ---
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown("### Discrepancy")
    tabs = st.tabs(["Comments", "AI Report Editor"])

    with tabs[1]:
        st.caption("Edit AI-generated DOCX reports directly. Download, edit with LibreOffice, and upload the edited version.")
        
        # DOCX detection from multiple possible fields (ai_url/ai_key/doctor_url/doctor_key)
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
            idx = labels_docx.index(selected_label) if selected_label in labels_docx else 0
            sel_ver = st.selectbox("AI report version (DOCX only)", options=labels_docx, index=idx, key=f"hist_editor_ver_{case_id}")
            chosen_url = docx_map.get(sel_ver)

            if chosen_url:
                # High‑fidelity Preview (Playwright — default)
                st.markdown("### High‑fidelity Preview (Playwright — default)")
                try:
                    import requests as _rq
                    headers = {"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"}
                    cache_key = f"pw_pdf_{case_id}_{(sel_ver or '').strip()}"
                    if cache_key not in st.session_state:
                        with st.spinner("Rendering DOCX via Playwright…"):
                            body = {"url": chosen_url, "case_id": case_id, "filename": f"{case_id}_{(sel_ver or 'docx').replace(' ', '_')}.pdf"}
                            r = _rq.post(f"{backend}/render/docx-to-pdf", json=body, headers=headers, timeout=180)
                            if r.ok:
                                data = r.json() or {}
                                st.session_state[cache_key] = data.get("url")
                            else:
                                st.session_state[cache_key] = None
                    pw_url = st.session_state.get(cache_key)
                    if pw_url:
                        st.markdown(f"<iframe src=\"{pw_url}\" width=\"100%\" height=\"650\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
                    else:
                        st.warning("Playwright renderer unavailable. Falling back to quick viewer.")
                        st.markdown(f"<iframe src=\"https://view.officeapps.live.com/op/embed.aspx?src={quote(chosen_url, safe='')}\" width=\"100%\" height=\"650\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
                except Exception:
                    st.markdown(f"<iframe src=\"https://view.officeapps.live.com/op/embed.aspx?src={quote(chosen_url, safe='')}\" width=\"100%\" height=\"650\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
                
                # Additional download option for convenience
                st.markdown("### Quick Actions")
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    if st.button("📥 Download Original DOCX", key=f"hist_download_{case_id}", type="primary"):
                        try:
                            import requests
                            # Use backend proxy to avoid CORS issues
                            proxy_url = f"{backend}/proxy/docx?url={quote(chosen_url, safe='')}"
                            response = requests.get(proxy_url, timeout=45)
                            if response.status_code == 200 and response.content:
                                st.download_button(
                                    "⬇️ Download Original",
                                    data=response.content,
                                    file_name=f"{case_id}_original_{sel_ver}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"hist_dl_{case_id}",
                                )
                                st.success("Original DOCX file ready for download!")
                            else:
                                # Fallback: try downloading directly from the DOCX URL
                                direct = requests.get(chosen_url, timeout=45)
                                if direct.ok and direct.content:
                                    st.download_button(
                                        "⬇️ Download Original",
                                        data=direct.content,
                                        file_name=f"{case_id}_original_{sel_ver}.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        key=f"hist_dl_direct_{case_id}",
                                    )
                                    st.info("Downloaded directly from source.")
                                else:
                                    st.error("Failed to download DOCX file")
                        except Exception as e:
                            st.error(f"Download failed: {str(e)}")
                
                with col2:
                    st.info("💡 **Edit in browser:**\nUse the editor above to edit the document content directly")

                st.markdown("### Upload edited DOCX back to S3")
                up_col1, up_col2 = st.columns([1, 1])
                with up_col1:
                    uploaded = st.file_uploader("Select edited DOCX", type=["docx"], key=f"hist_docx_upl_{case_id}")
                with up_col2:
                    # Filename locked to original basename with _edited suffix (strip any S3 path prefix)
                    _orig = (sel_ver or "report").split("/")[-1]
                    if _orig.lower().endswith('.docx'):
                        target_name = _orig[:-5] + "_edited.docx"
                    else:
                        target_name = _orig + "_edited.docx"
                    st.text_input("Target filename", value=target_name, key=f"hist_docx_name_{case_id}", disabled=True)

                def _try_presign_and_upload(_backend: str, _case_id: str, _fname: str, _bytes: bytes) -> tuple[bool, str | None]:
                    try:
                        import requests as _rq
                        headers = {"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"}
                        # Try a few common endpoints for presign
                        candidates = [
                            ("POST", f"{_backend}/s3/upload-ai"),
                            ("POST", f"{_backend}/s3/presign"),
                        ]
                        presigned = None
                        for method, url in candidates:
                            try:
                                body = {"case_id": _case_id, "type": "ai", "filename": _fname}
                                r = _rq.post(url, json=body, headers=headers, timeout=15)
                                if r.ok:
                                    data = r.json() or {}
                                    if data.get("url"):
                                        presigned = data
                                        break
                            except Exception:
                                continue
                        if not presigned:
                            # Fallback: direct upload endpoint (multipart)
                            try:
                                files = {"file": (_fname, _bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                                r2 = _rq.post(f"{_backend}/upload/ai", files=files, data={"case_id": _case_id, "filename": _fname}, timeout=30, headers={"ngrok-skip-browser-warning": "true"})
                                if r2.ok:
                                    return True, (r2.json() or {}).get("key") or None
                            except Exception:
                                pass
                            return False, None
                        # Upload with PUT (common) or POST (form)
                        url = presigned.get("url")
                        method = (presigned.get("method") or "PUT").upper()
                        if method == "POST" and isinstance(presigned.get("fields"), dict):
                            form = presigned["fields"]
                            files = {"file": (_fname, _bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                            r3 = _rq.post(url, data=form, files=files, timeout=60)
                            return (r3.ok, presigned.get("key"))
                        else:
                            # Default to PUT
                            # Note: some presigned URLs fail if Content-Type is set; try without first
                            r3 = _rq.put(url, data=_bytes, timeout=60)
                            if not r3.ok:
                                # Retry with content-type header
                                r3 = _rq.put(url, data=_bytes, headers={"Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}, timeout=60)
                            return (r3.ok, presigned.get("key"))
                    except Exception as _e:
                        return False, None

                if uploaded and st.button("Upload edited DOCX", type="primary", key=f"hist_docx_upload_btn_{case_id}"):
                    try:
                        content = uploaded.read()
                        ok, key = _try_presign_and_upload(backend, case_id, target_name.strip(), content)
                        if ok:
                            st.success("Uploaded successfully to S3.")
                            # Optionally refresh outputs list next run
                            try:
                                st.cache_data.clear()
                            except Exception:
                                pass
                        else:
                            st.error("Upload failed. Please try again later or contact support.")
                    except Exception as e:
                        import traceback
                        st.error(f"Upload error: {str(e)}")
                        st.caption(traceback.format_exc())

                # Debug upload endpoints section removed

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

    # Comment input UI is rendered inside the Comments tab below.

    with tabs[0]:
        st.caption("Record mismatches between Ground Truth and AI by section and subsection.")
        # --- Add comment form (inside Comments tab only; always visible) ---
        st.markdown("#### Add comment")
        section_options = list(toc_sections.keys())
        cfrm1, cfrm2 = st.columns([3, 1])
        with cfrm1:
            hierarchical_options: list[str] = []
            section_to_subsection: dict[str, str] = {}
        for section in section_options:
            subsections = toc_sections.get(section, [])
            if subsections:
                hierarchical_options.append(section)
                section_to_subsection[section] = section
                for sub in subsections:
                        indented = f"    └─ {sub}"
                        hierarchical_options.append(indented)
                        section_to_subsection[indented] = section
            else:
                hierarchical_options.append(section)
                section_to_subsection[section] = section
        form_section = st.selectbox(
            "Section/Subsection",
            options=hierarchical_options,
            index=0,
            key="comments_form_section",
        )
        with cfrm2:
            form_severity = st.selectbox("Severity", options=["Low", "Medium", "High"], index=1, key="comments_form_severity")

        form_text = st.text_area("Describe the discrepancy", key="comments_form_text")
        submit_col, _ = st.columns([0.25, 0.75])
        with submit_col:
            if st.button("Add comment", type="primary", key="comments_form_submit"):
                if form_text.strip():
        try:
            import requests as _rq
                        backend = st.session_state.get("backend_url", "http://localhost:8000")
                        if form_section.startswith("    └─ "):
                                subsection = form_section.replace("    └─ ", "")
                                section = section_to_subsection[form_section]
            else:
                            section = form_section
                            subsection = form_section
            payload = {
                "case_id": case_id,
                "ai_label": selected_label or None,
                "section": section,
                "subsection": subsection,
                                                            "username": st.session_state.get("username") or "anonymous",
                                                            "severity": form_severity,
                                                            "comment": form_text.strip(),
            }
            _rq.post(f"{backend}/comments", json=payload, timeout=8)
            _get_case_comments.clear()
            st.success("Added.")
        except Exception:
            st.warning("Failed to add comment.")
            else:
                                    st.warning("Please enter a comment.")

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        st.markdown("#### Recorded comments")
    # List comments (cached)
    notes = _get_case_comments(backend, case_id, selected_label)
    # Render notes table only when there are comments; add pagination (10 per page)
    page_size = 10
    total = len(notes)
    if total > 0:
        total_pages = max(1, (total + page_size - 1) // page_size)
        # Track current page in session (per-case)
        pg_key = f"hist_notes_page_{case_id}"
        cur_page = int(st.session_state.get(pg_key, 1))
        # Controls
        cprev, cinfo, cnext = st.columns([1, 2, 1])
        with cprev:
            if st.button("← Prev", disabled=(cur_page <= 1)):
                cur_page = max(1, cur_page - 1)
        with cinfo:
            st.markdown(f"<div style='text-align:center;opacity:.85;'>Page {cur_page} of {total_pages}</div>", unsafe_allow_html=True)
        with cnext:
            if st.button("Next →", disabled=(cur_page >= total_pages)):
                cur_page = min(total_pages, cur_page + 1)
        st.session_state[pg_key] = cur_page

        # Slice items for current page
        start_idx = (cur_page - 1) * page_size
        end_idx = min(total, start_idx + page_size)
        page_items = notes[start_idx:end_idx]
    else:
        page_items = []

    if page_items:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        st.markdown("**Recorded comments**")
        # Header row
        h1, h2, h3, h4, h5, h6 = st.columns([2.0, 0.7, 0.6, 1.8, 2.8, 1.2])
        h1.markdown("**Section/Subsection**")
        h2.markdown("**User**")
        h3.markdown("**Severity**")
        h4.markdown("**When**")
        h5.markdown("**Comment**")
        h6.markdown("**Actions**")

        # Rows with inline action buttons in the last column
        for n in page_items:
            nid = n.get("id")
            is_resolved = bool(n.get("resolved"))
            section = n.get('section') or '—'
            subsection = n.get("subsection") or (toc_sections.get(n.get("section") or "", [])[:1] or [n.get("section")])[0]
            combined = f"{section} / {subsection}" if subsection and subsection != '—' else section
            when = (n.get("created_at") or "").replace("T", " ").replace("Z", " UTC")
            usernm = n.get("username") or "anonymous"
            sev = n.get("severity") or "—"

            c1, c2, c3, c4, c5, c6 = st.columns([2.0, 0.7, 0.6, 1.8, 2.8, 1.2])
            c1.markdown(combined)
            c2.markdown(usernm)
            c3.markdown(sev)
            c4.markdown(when or '—')
            c5.markdown((n.get('comment') or '').strip() or '—')
            with c6:
                act1, act2 = st.columns([0.6, 0.4])
                with act1:
                    label = ("✓ Resolve" if not is_resolved else "✗ Unresolve")
                    if st.button(label, key=f"row_resolve_{nid}") and nid:
                        try:
                            import requests as _rq
                            _rq.patch(f"{backend}/comments/resolve", json={"id": int(nid), "case_id": case_id, "resolved": (not is_resolved)}, timeout=8, headers={"ngrok-skip-browser-warning": "true"})
                            _get_case_comments.clear()
                        except Exception:
                            pass
                        st.rerun()
                with act2:
                    if st.button("🗑️", key=f"row_delete_{nid}") and nid:
                        try:
                            import requests as _rq
                            _rq.delete(f"{backend}/comments", json={"case_id": case_id, "ai_label": selected_label, "ids": [int(nid)]}, timeout=8, headers={"ngrok-skip-browser-warning": "true"})
                            _get_case_comments.clear()
                        except Exception:
                            pass
                        st.rerun()
    elif total == 0:
        st.info("No comments yet.")

if __name__ == "__main__":
    main()