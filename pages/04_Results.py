import streamlit as st
from datetime import datetime
from app.ui import inject_base_styles, theme_provider
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
    
    ensure_authenticated()

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

    # Toolbar: Save to history (explicit)
    t1, t2 = st.columns([0.8, 0.2])
    with t2:
        uname = st.session_state.get("username") or st.session_state.get("name")
        disabled = not bool(uname)
        if disabled:
            st.caption("Login required to save")
        if st.button("Save to history", key="v2_save_hist", use_container_width=True, disabled=disabled):
            try:
                r = requests.post(f"{backend}/history/{case_id}/sync", params={"username": uname}, timeout=10)
                if r.ok:
                    st.success("Saved")
                else:
                    st.warning("Could not save")
            except Exception:
                st.warning("Could not save")

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

    # Debug panel removed

    # Build layout first with placeholders
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Ground Truth**")
        st.markdown("<div style='opacity:.75;margin:.25rem 0 .5rem;'>Original document preview</div>", unsafe_allow_html=True)
        st.markdown("<div style='opacity:.65;margin-top:-6px;'>• Converted to PDF from DOCX</div>", unsafe_allow_html=True)
        st.markdown("<div style='opacity:.65;margin-top:-2px;margin-bottom:.35rem;'>• Falls back to DOCX download if needed</div>", unsafe_allow_html=True)
        gt_area = st.empty()
    with col2:
        st.markdown("**AI Generated**")
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
        st.markdown("**Doctor as LLM**")
        st.markdown("<div style='opacity:.75;margin:.25rem 0 .5rem;'>Paired doctor-as-LLM report</div>", unsafe_allow_html=True)
        st.markdown("<div style='opacity:.65;margin-top:-6px;margin-bottom:.35rem;'>• This report can be changed by</div>", unsafe_allow_html=True)
        st.markdown("<div style='opacity:.65;margin-top:-6px;margin-bottom:.35rem;'>  changing the AI genreated report</div>", unsafe_allow_html=True)
        doc_area = st.empty()

    # Fetch ground truth separately using existing assets endpoint (latest)
    assets = {}
    gt_pdf = None
    gt_generic = None
    gt_effective_pdf_url = None
    try:
        r = requests.get(f"{backend}/s3/{case_id}/latest/assets", timeout=10)
        if r.ok:
            assets = r.json() or {}
            gt_pdf = assets.get("ground_truth_pdf")
            gt_generic = assets.get("ground_truth")
    except Exception:
        pass

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
    if sel_ai and sel_ai.get("ai_url"):
        with col2:
            _iframe(sel_ai["ai_url"])
        ai_effective_pdf_url = sel_ai["ai_url"]
    else:
        with col2:
            st.info("Not available")

    doc_pdf = sel_ai.get("doctor_url") if sel_ai else None
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


if __name__ == "__main__":
    main()


