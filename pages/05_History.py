import streamlit as st
from app.ui import inject_base_styles, theme_provider
import os
import streamlit.components.v1 as components
from urllib.parse import quote


def _get_qp(name: str) -> str | None:
    try:
        if hasattr(st, "query_params"):
            val = st.query_params.get(name)
            return val[0] if isinstance(val, list) else val
        get_qp = getattr(st, "experimental_get_query_params", None)
        if callable(get_qp):
            vals = get_qp().get(name)
            return vals[0] if isinstance(vals, list) and vals else None
    except Exception:
        return None
    return None


def _backend() -> str:
    qp = _get_qp("api")
    return (qp or os.getenv("BACKEND_BASE") or "http://localhost:8000").rstrip("/")

def _extract_patient(case_id: str, gt_key: str | None = None, ai_label: str | None = None, doc_label: str | None = None) -> str | None:
    try:
        import re
        if gt_key:
            m = re.search(r"_LCP_([^_/]+?)_", gt_key)
            if m:
                return m.group(1).replace("_", " ")
        label = ai_label or doc_label
        if label and case_id:
            m = re.search(rf"-?{case_id}-([^-_]+)", label)
            if m:
                raw = m.group(1)
                parts = re.findall(r"[A-Z][a-z]*", raw)
                return " ".join(parts) if parts else raw
    except Exception:
        return None
    return None

def main() -> None:
    st.set_page_config(page_title="History", page_icon="🕘", layout="wide")
    theme_provider()
    inject_base_styles()

    backend = _backend()

    try:
        import requests
    except Exception:
        st.error("Requests not available.")
        return

    # Load per-user cases and present a dropdown
    uname = st.session_state.get("username") or st.session_state.get("name")
    try:
        rc = requests.get(f"{backend}/history/cases", params={"username": uname}, timeout=8)
        cases = (rc.json() or {}).get("cases", []) if rc.ok else []
    except Exception:
        cases = []

    st.markdown("## History")
    st.caption("Select a saved case to view up to 3 AI reports.")
    if not cases:
        st.info("No saved cases yet. Open Results Page and click ‘Save to history’.")
        return

    # Build display labels like "3337 : FatimaDodson" by peeking first snapshot per case
    display_to_case: dict[str, str] = {}
    options: list[str] = []
    for cid in cases:
        try:
            r = requests.get(f"{backend}/history/{cid}", params={"username": uname}, timeout=8)
            items_preview = (r.json() or {}).get("items", []) if r.ok else []
        except Exception:
            items_preview = []
        patient = None
        if items_preview:
            first = items_preview[0]
            patient = _extract_patient(cid, gt_key=first.get("ground_truth_key"), ai_label=first.get("label"))
        label = f"{cid} : {patient}" if patient else cid
        display_to_case[label] = cid
        options.append(label)

    sel_display = st.selectbox("Saved cases", options=options, key="hist_case_select")
    sel_case = display_to_case.get(sel_display, cases[0])
    if not sel_case:
        return

    # Fetch snapshots for selected case
    items: list[dict] = []
    try:
        r = requests.get(f"{backend}/history/{sel_case}", params={"username": uname}, timeout=8)
        if r.ok:
            data = r.json() or {}
            items = data.get("items", []) or []
    except Exception:
        items = []

    if not items:
        st.info("No snapshots saved for this case yet.")
        return

    # Sort by created_at descending if available
    def _k(it: dict) -> str:
        return it.get("created_at") or ""
    items = sorted(items, key=_k, reverse=True)

    col1, col2, col3 = st.columns(3)

    # Ground Truth (left) — mirror Results page logic exactly
    assets = {}
    gt_pdf = None
    gt_generic = None
    gt_effective_pdf_url = None
    try:
        r_assets = requests.get(f"{backend}/s3/{sel_case}/latest/assets", timeout=10)
        if r_assets.ok:
            assets = r_assets.json() or {}
            gt_pdf = assets.get("ground_truth_pdf")
            gt_generic = assets.get("ground_truth")
    except Exception:
        pass

    with col1:
        st.markdown("**Ground Truth**")
        st.markdown("<div style='opacity:.75;margin:.25rem 0 .5rem;'>Original document preview</div>", unsafe_allow_html=True)
        st.markdown("<div style='opacity:.65;margin-top:-6px;'>• Converted to PDF from DOCX</div>", unsafe_allow_html=True)
        st.markdown("<div style='opacity:.65;margin-top:-2px;margin-bottom:.35rem;'>• Falls back to DOCX download if needed</div>", unsafe_allow_html=True)
        if gt_pdf:
            st.markdown(f"<iframe src=\"{gt_pdf}\" width=\"100%\" height=\"520\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
            gt_effective_pdf_url = gt_pdf
        elif gt_generic:
            raw_key = assets.get("ground_truth_key") if isinstance(assets, dict) else None
            params = {"key": raw_key} if raw_key else {"url": gt_generic}
            try:
                r2 = requests.get(f"{backend}/s3/ensure-pdf", params=params, timeout=10)
                if r2.ok:
                    data2 = r2.json() or {}
                    url2 = data2.get("url")
                    fmt = data2.get("format")
                    if fmt == "pdf" and url2:
                        st.markdown(f"<iframe src=\"{url2}\" width=\"100%\" height=\"520\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
                        gt_effective_pdf_url = url2
                    else:
                        st.markdown(f"<a href=\"{url2 or gt_generic}\" target=\"_blank\" class=\"st-a\">📥 Download Ground Truth</a>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<a href=\"{gt_generic}\" target=\"_blank\" class=\"st-a\">📥 Download Ground Truth</a>", unsafe_allow_html=True)
            except Exception:
                st.markdown(f"<a href=\"{gt_generic}\" target=\"_blank\" class=\"st-a\">📥 Download Ground Truth</a>", unsafe_allow_html=True)
        else:
            st.info("Not available")

    # AI select (middle)
    with col2:
        st.markdown("**AI Generated**")
        labels = []
        label_to_item = {}
        for it in items:
            lab = it.get("label") or (it.get("ai_key") or "").split("/")[-1]
            if lab and lab not in label_to_item:
                label_to_item[lab] = it
                labels.append(lab)
        sel_it = None
        if labels:
            sel_label = st.selectbox("Select AI output", options=labels, key="hist_ai_select")
            sel_it = label_to_item.get(sel_label)
        else:
            st.caption("No saved AI outputs for this case.")

        ai_url = None
        if sel_it and sel_it.get("ai_key"):
            try:
                pr = requests.get(f"{backend}/cache/presign", params={"key": sel_it.get("ai_key")}, timeout=6)
                if pr.ok:
                    ai_url = (pr.json() or {}).get("url")
            except Exception:
                pass
        ai_effective_pdf_url = None
        if ai_url:
            st.markdown(f"<iframe src=\"{ai_url}\" width=\"100%\" height=\"520\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
            ai_effective_pdf_url = ai_url
        else:
            st.info("Not available")

    # Doctor (right) matching selected AI
    with col3:
        st.markdown("**Doctor as LLM**")
        st.markdown("<div style='opacity:.75;margin:.25rem 0 .5rem;'>Paired doctor-as-LLM report</div>", unsafe_allow_html=True)
        st.markdown("<div style='opacity:.65;margin-top:-6px;'>• Matched to the selected AI run</div>", unsafe_allow_html=True)
        st.markdown("<div style='opacity:.65;margin-top:-2px;'>• View inline or download</div>", unsafe_allow_html=True)
        # st.markdown("<div style='opacity:.65;margin-top:-2px;margin-bottom:.35rem;'>• Source: S3 Output/</div>", unsafe_allow_html=True)
        # Show patient name parsed from saved labels/keys
        try:
            from pages import _04_Results as results  # type: ignore
            _extract = getattr(results, "_extract_patient_from_strings", None)
        except Exception:
            _extract = None
        if _extract and ("sel_label" in locals() or gt_url):
            try:
                patient = _extract(sel_case, gt_key=gk if 'gk' in locals() else None, ai_label=sel_label if 'sel_label' in locals() else None)
                if patient:
                    st.caption(f"Patient: {patient}")
            except Exception:
                pass
        doc_url = None
        if sel_it and sel_it.get("doctor_key"):
            try:
                pr = requests.get(f"{backend}/cache/presign", params={"key": sel_it.get("doctor_key")}, timeout=6)
                if pr.ok:
                    doc_url = (pr.json() or {}).get("url")
            except Exception:
                pass
        if doc_url:
            st.markdown(f"<iframe src=\"{doc_url}\" width=\"100%\" height=\"520\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
        else:
            st.info("Not available")

    # Synchronized scrolling (Ground Truth ↔ AI Generated)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    enable_sync = st.checkbox("Enable synchronized scrolling (Ground Truth ↔ AI Generated)", value=False, key="hist_sync")
    if enable_sync and gt_effective_pdf_url and ai_effective_pdf_url:
        sync_height = 640
        html = """
        <div style=\"display:grid;grid-template-columns:1fr 1fr;gap:12px;\"> 
          <div id=\"leftPane\" style=\"height:__H__px;overflow:auto;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:6px;\"></div>
          <div id=\"rightPane\" style=\"height:__H__px;overflow:auto;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:6px;\"></div>
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
        function linkScroll(a, b) {
          a.addEventListener('scroll', () => {
            if (syncing) return;
            syncing = true;
            const ratio = a.scrollTop / (a.scrollHeight - a.clientHeight || 1);
            b.scrollTop = ratio * (b.scrollHeight - b.clientHeight);
            syncing = false;
          }, { passive: true });
        }

        (async () => {
          await Promise.all([
            renderPdf('__GT__', 'leftPane'),
            renderPdf('__AI__', 'rightPane')
          ]);
          const left = document.getElementById('leftPane');
          const right = document.getElementById('rightPane');
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
        html = html.replace("__GT__", proxy_gt).replace("__AI__", proxy_ai)
        components.html(html, height=sync_height + 16)


if __name__ == "__main__":
    main()


