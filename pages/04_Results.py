
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
        # Ground truth like: 3337_LCP_Fatima Dodson_....docx
        if gt_key:
            m = re.search(r"_LCP_([^_/]+?)_", gt_key)
            if m:
                return m.group(1).replace("_", " ")
        # AI like: 202508281810-3337-FatimaDodson-CompleteAIGenerated.pdf
        label = ai_label or doc_label
        if label and case_id:
            m = re.search(rf"-?{case_id}-([^-_]+)", label)
            if m:
                raw = m.group(1)
                # Split CamelCase e.g., BlancaOrtiz -> Blanca Ortiz
                parts = re.findall(r"[A-Z][a-z]*", raw)
                return " ".join(parts) if parts else raw
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
    # Page-scoped compact buttons for action cells
    st.markdown(
        """
        <style>
        .stButton > button { font-size: 0.85rem; padding: .25rem .55rem; }
        @media (max-width: 1100px) { .stButton > button { font-size: 0.80rem; padding: .2rem .5rem; } }
        @media (max-width: 900px) { .stButton > button { font-size: 0.78rem; padding: .18rem .45rem; } }
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
    # Debug: show logged-in user (matches Case Report UX)
    if st.session_state.get("username") or st.session_state.get("name"):
        _uname = st.session_state.get("username") or st.session_state.get("name")
        st.info(f"👤 Logged in as: {_uname}")

    # Top nav with History
    top_nav(active="Results")

    case_id = (
        st.session_state.get("last_case_id")
        or st.session_state.get("current_case_id")
        or _qp_get("case_id", "0000")
    )
    backend = _get_backend_base()

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
        r = requests.get(f"{backend}/s3/{case_id}/outputs", timeout=8)
        if r.ok:
            data = r.json() or {}
            outputs = data.get("items", []) or []
    except Exception:
        outputs = []

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

        # Code version: prefer value captured in session; otherwise fetch
        import os as _os, json as _json, base64 as _b64
        try:
            import requests as _rq
            sess_ver = (st.session_state.get("code_version_by_case") or {}).get(str(case_id)) or st.session_state.get("code_version")
            if not sess_ver:
                # Try to parse last webhook text if it contained the array output
                try:
                    _last = st.session_state.get("last_webhook_text")
                    if _last:
                        _data = _json.loads(_last)
                        if isinstance(_data, list) and _data:
                            _v = _data[0].get("Version") or _data[0].get("version")
                            if isinstance(_v, str):
                                sess_ver = _v.replace(".json", "")
                except Exception:
                    pass
            if sess_ver:
                code_version = sess_ver
            else:
                _ver_url = _os.getenv(
                    "VERSION_FILE_API_URL",
                    "https://api.github.com/repos/Samarth0211/n8n-workflows-backup/contents/state/w46R1cer565OMr9u.version?ref=main",
                )
                @st.cache_data(ttl=300)
                def _fetch_code_version(url: str) -> str:
                    r = _rq.get(url, timeout=6)
                    if r.ok:
                        try:
                            data = r.json()
                        except Exception:
                            return "—"
                        if isinstance(data, list) and data:
                            val = data[0].get("Version") or data[0].get("version")
                            if isinstance(val, str):
                                return val.replace(".json", "")
                        if isinstance(data, dict):
                            content = data.get("content")
                            enc = data.get("encoding")
                            if content and (enc or "").lower() == "base64":
                                raw = _b64.b64decode(content).decode("utf-8", "ignore")
                                j = _json.loads(raw)
                                val = j.get("version", "—")
                                return val.replace(".json", "") if isinstance(val, str) else "—"
                            val = data.get("version")
                            if isinstance(val, str):
                                return val.replace(".json", "")
                    return "—"
                code_version = _fetch_code_version(_ver_url)
        except Exception:
            code_version = "—"
        generated_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        rows: list[tuple[str, str, str, str | None, str | None, str | None]] = []
        if outputs:
            for o in outputs:
                doc_version = extract_version(o.get("label"))
                rows.append((generated_ts, code_version, doc_version, gt_effective_pdf_url, o.get("ai_url"), o.get("doctor_url")))
        else:
            rows.append((generated_ts, code_version, "—", gt_effective_pdf_url, None, None))

        table_html = [
            '<div style="border:1px solid rgba(255,255,255,0.12);border-radius:8px;overflow:hidden;margin-top:12px;">',
            '<div style="display:grid;grid-template-columns:220px 160px 150px 1fr 1fr 1fr;gap:0;border-bottom:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);">',
            '<div style="padding:.5rem .75rem;font-weight:700;">Report Generated</div>',
            '<div style="padding:.5rem .75rem;font-weight:700;">Code Version</div>',
            '<div style="padding:.5rem .75rem;font-weight:700;">Document Version</div>',
            '<div style="padding:.5rem .75rem;font-weight:700;">Ground Truth</div>',
            '<div style="padding:.5rem .75rem;font-weight:700;">AI Generated</div>',
            '<div style="padding:.5rem .75rem;font-weight:700;">Doctor as LLM</div>',
            '</div>'
        ]
        for (gen_time, code_ver, doc_ver, gt_url, ai_url, doc_url) in rows:
            gt_dl = dl_link(gt_url)
            ai_dl = dl_link(ai_url)
            doc_dl = dl_link(doc_url)
            gt_link = f'<a href="{gt_dl}" class="st-a" download>{file_name(gt_url)}</a>' if gt_dl else '<span style="opacity:.6;">—</span>'
            ai_link = f'<a href="{ai_dl}" class="st-a" download>{file_name(ai_url)}</a>' if ai_dl else '<span style="opacity:.6;">—</span>'
            doc_link = f'<a href="{doc_dl}" class="st-a" download>{file_name(doc_url)}</a>' if doc_dl else '<span style="opacity:.6;">—</span>'
            
            # Append each row element individually
            table_html.append('<div style="display:grid;grid-template-columns:220px 160px 150px 1fr 1fr 1fr;gap:0;border-bottom:1px solid rgba(255,255,255,0.06);">')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;">{gen_time}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;">{code_ver}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;opacity:.9;">{doc_ver}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;">{gt_link}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;">{ai_link}</div>')
            table_html.append(f'<div style="padding:.5rem .75rem;">{doc_link}</div>')
            table_html.append('</div>')
        table_html.append('</div>')
        st.markdown("".join(table_html), unsafe_allow_html=True)
        # Extra breathing room below the summary table
        st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
    except Exception:
        pass

    # Build layout after table
    # Build layout first with placeholders
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
        gt_area = st.empty()
    with col2:
        st.markdown(
            """
            <div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.15rem;margin-left:8px;'>
              <span style="display:inline-block;padding:.15rem .5rem;border-radius:999px;background:rgba(139,92,246,0.15);border:1px solid rgba(139,92,246,0.35);color:#c4b5fd;font-size:.8rem;font-weight:700;letter-spacing:.02em;">AI</span>
              <span style='font-weight:700;'>AI Generated</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if outputs:
            labels = [o.get("label") for o in outputs if o.get("label")]
            default_idx = 0
            if "v2_ai_label" in st.session_state and st.session_state["v2_ai_label"] in labels:
                default_idx = labels.index(st.session_state["v2_ai_label"])
            selected_label = st.selectbox("Select AI output", options=labels, index=default_idx, key="v2_ai_label")
        else:
            st.caption("No AI outputs found under Output/ for this case.")
            selected_label = None
        ai_area = st.empty()
    with col3:
        st.markdown(
            """
            <div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.15rem;margin-left:8px;'>
              <span style="display:inline-block;padding:.15rem .5rem;border-radius:999px;background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.35);color:#86efac;font-size:.8rem;font-weight:700;letter-spacing:.02em;">DR</span>
              <span style='font-weight:700;'>Doctor as LLM</span>
            </div>
            <div style='opacity:.75;margin:.25rem 0 .5rem;'>Paired doctor-as-LLM report</div>
            <div style='opacity:.65;margin-top:-6px;margin-bottom:.35rem;'>• This report can be changed by</div>
            <div style='opacity:.65;margin-top:-6px;margin-bottom:.35rem;'>  changing the AI genreated report</div>
            """,
            unsafe_allow_html=True,
        )
        doc_area = st.empty()

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
    if gt_pdf:
        with col1:
            _iframe(gt_pdf)
        gt_effective_pdf_url = gt_pdf
    elif gt_generic:
        with col1:
            # Try converting by key if provided by backend, else by URL
            raw_key = assets.get("ground_truth_key") if isinstance(assets, dict) else None
            params = {"key": raw_key} if raw_key else {"url": gt_generic}
            try:
                r2 = requests.get(f"{backend}/s3/ensure-pdf", params=params, timeout=10)
                if r2.ok:
                    data2 = r2.json() or {}
                    url2 = data2.get("url")
                    fmt = data2.get("format")
                    if fmt == "pdf" and url2:
                        _iframe(url2)
                        gt_effective_pdf_url = url2
                    else:
                        st.markdown(f"<a href=\"{url2 or gt_generic}\" target=\"_blank\" class=\"st-a\">📥 Download Ground Truth</a>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<a href=\"{gt_generic}\" target=\"_blank\" class=\"st-a\">📥 Download Ground Truth</a>", unsafe_allow_html=True)
            except Exception:
                st.markdown(f"<a href=\"{gt_generic}\" target=\"_blank\" class=\"st-a\">📥 Download Ground Truth</a>", unsafe_allow_html=True)
    else:
        with col1:
            st.info("Not available")

    # Render AI/Doctor using outputs list selection
    sel_ai = None
    if selected_label:
        for o in outputs:
            if o.get("label") == selected_label:
                sel_ai = o
                break
    ai_effective_pdf_url = None
    # Prefer immediate AI URL from session (webhook response), else from outputs
    ai_url_from_session = (st.session_state.get("ai_signed_url_by_case", {}) or {}).get(str(case_id))
    if ai_url_from_session:
        with col2:
            _iframe(ai_url_from_session)
        ai_effective_pdf_url = ai_url_from_session
    elif sel_ai and sel_ai.get("ai_url"):
        with col2:
            _iframe(sel_ai["ai_url"])
        ai_effective_pdf_url = sel_ai["ai_url"]
    else:
        with col2:
            st.info("Not available")

    # Attempt to find a matching Doctor-as-LLM file
    doc_pdf = None
    if sel_ai and sel_ai.get("doctor_url"):
        doc_pdf = sel_ai.get("doctor_url")
    else:
        # Heuristic: match by prefix timestamp of AI label in outputs
        try:
            import re
            ai_label = (sel_ai or {}).get("label") or (st.session_state.get("ai_label_by_case", {}) or {}).get(str(case_id))
            if ai_label:
                m = re.match(r"^(\d{12})", ai_label)
                if m:
                    prefix = m.group(1)
                    for o in outputs:
                        doc_label = o.get("doctor_label") or o.get("label") or ""
                        if isinstance(doc_label, str) and doc_label.startswith(prefix) and o.get("doctor_url"):
                            doc_pdf = o.get("doctor_url")
                            break
        except Exception:
            pass
    doc_effective_pdf_url = None
    if doc_pdf:
        with col3:
            _iframe(doc_pdf)
        doc_effective_pdf_url = doc_pdf
    else:
        with col3:
            st.info("Not available")

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
        sync_height = 640
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
        let lockedScrollRatio = 0; // Store the ratio when locking
        
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
          const left = document.getElementById('leftPane');
          const right = document.getElementById('rightPane');
          
          // Don't change positions - just enable synchronization from current positions
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


    # --- Discrepancy notes & export ---
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown("### Discrepancy Notes")
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
    
    ncol1, ncol2, ncol3 = st.columns([2, 2, 1])
    with ncol1:
        section_choice = st.selectbox("Section", options=section_options, index=0)
    with ncol2:
        # Get subsections for selected section
        subsections = toc_sections.get(section_choice, [])
        if subsections:
            subsection_choice = st.selectbox("Subsection", options=subsections, index=0)
        else:
            # If no predefined subsections, allow free text; we'll default later
            subsection_choice = st.text_input("Subsection (if none available)", value="", key="disc_subsection")
    with ncol3:
        severity = st.selectbox("Severity", options=["Low", "Medium", "High"], index=1)

    comment = st.text_area("Describe the discrepancy", placeholder="e.g., Missing 'Lisinopril' in medications section compared to ground truth.", key="disc_comment")
    meta_cols = st.columns([0.2, 0.8])
    with meta_cols[0]:
        add_ok = st.button("Add comment", type="primary", key="disc_add_btn")
    with meta_cols[1]:
        st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)

    if add_ok and section_choice and comment:
        # Persist to backend (shared)
        try:
            if requests is not None:
                # Ensure subsection is never empty: default to first option or section name
                _sub = subsection_choice.strip() if isinstance(subsection_choice, str) else subsection_choice
                if not _sub:
                    _sub = (subsections[0] if subsections else section_choice)
                _user = current_user
                payload = {
                    "case_id": case_id,
                    "ai_label": selected_label or None,
                    "section": section_choice,
                    "subsection": _sub,
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
        # Header row
        h1, h2, h3, h4, h5, h6 = st.columns([1.0, 1.0, 0.7, 0.6, 2.0, 0.5])
        with h1: st.markdown("<div style='font-weight:700;'>Section</div>", unsafe_allow_html=True)
        with h2: st.markdown("<div style='font-weight:700;'>Subsection</div>", unsafe_allow_html=True)
        with h3: st.markdown("<div style='font-weight:700;'>User</div>", unsafe_allow_html=True)
        with h4: st.markdown("<div style='font-weight:700;'>Severity</div>", unsafe_allow_html=True)
        with h5: st.markdown("<div style='font-weight:700;'>When</div>", unsafe_allow_html=True)
        with h6: st.markdown("<div style='font-weight:700;'>Delete</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin-top:4px;margin-bottom:6px;opacity:.15;'>", unsafe_allow_html=True)

        # Rows with in-line actions
        for n in notes:
            is_resolved = bool(n.get("resolved"))
            row_style = "opacity:.85;background:rgba(255,255,255,0.03);border-radius:6px;padding:.2rem .35rem;" if is_resolved else ""
            text_style = "opacity:.7;color:#9aa0a6;" if is_resolved else ""
            st.markdown(f"<div style='{row_style}'></div>", unsafe_allow_html=True)
            c1, c2, c3, c4, c5, c6 = st.columns([1.0, 1.0, 0.7, 0.6, 2.0, 1.2])
            with c1:
                st.markdown(f"<div style='{text_style}'>{n.get('section','') or '—'}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div style='{text_style}'>{n.get('subsection','') or '—'}</div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div style='{text_style}'>{n.get('username') or '—'}</div>", unsafe_allow_html=True)
            with c4:
                st.markdown(f"<div style='{text_style}'>{n.get('severity','') or '—'}</div>", unsafe_allow_html=True)
            with c5:
                when = (n.get("ts", "") or "").replace("T", " ").replace("Z", " UTC")
                st.markdown(f"<div style='{text_style}'>{when or '—'}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{text_style};font-size:.85rem;opacity:.75;'>{n.get('comment','') or ''}</div>", unsafe_allow_html=True)
            with c6:
                nid = n.get("id")
                # Resolve button (anyone can mark)
                cols_act = st.columns([0.6, 0.4])
                with cols_act[0]:
                    label = ("Resolve\u00A0\u00A0\u00A0" if not is_resolved else "Unresolve\u00A0\u00A0")
                    if nid and st.button(label, key=f"disc_res_{nid}"):
                        try:
                            if requests is not None:
                                payload = {"id": int(nid), "case_id": case_id, "resolved": (not is_resolved)}
                                requests.patch(f"{backend}/comments/resolve", json=payload, timeout=8)
                        except Exception:
                            pass
                        st.rerun()
                # Delete only for author
                with cols_act[1]:
                    can_delete = (n.get("username") or "") == (st.session_state.get("username") or st.session_state.get("name") or "")
                    if nid and can_delete and st.button("Delete", key=f"disc_del_{nid}"):
                        try:
                            if requests is not None:
                                payload = {"case_id": case_id, "ai_label": selected_label, "ids": [int(nid)]}
                                requests.delete(f"{backend}/comments", json=payload, timeout=8)
                        except Exception:
                            pass
                        st.rerun()

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


