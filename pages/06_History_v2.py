import streamlit as st
import os
import streamlit.components.v1 as components
from urllib.parse import quote
from app.ui import inject_base_styles, theme_provider, top_nav


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


@st.cache_data(show_spinner=False)
def _case_to_patient_map(backend: str, cases: list[str]) -> dict[str, str]:
    """Build a mapping of case_id -> patient name (best-effort)."""
    try:
        import requests
    except Exception:
        return {}
    out: dict[str, str] = {}
    for cid in cases:
        name: str | None = None
        # Try outputs first (labels carry patient name often)
        try:
            r = requests.get(f"{backend}/s3/{cid}/outputs", timeout=6)
            if r.ok:
                items = (r.json() or {}).get("items", []) or []
                if items:
                    name = _extract_patient_from_strings(cid, ai_label=items[0].get("label"))
        except Exception:
            pass
        # Fallback to assets ground truth key
        if not name:
            try:
                r2 = requests.get(f"{backend}/s3/{cid}/latest/assets", timeout=6)
                if r2.ok:
                    assets = r2.json() or {}
                    name = _extract_patient_from_strings(cid, gt_key=assets.get("ground_truth_key"))
            except Exception:
                pass
        if name:
            out[cid] = name
    return out


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def main() -> None:
    st.set_page_config(page_title="History v2 (All Cases)", page_icon="🗂️", layout="wide")
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

    # Nav bar
    top_nav(active="History")

    try:
        import requests
    except Exception:
        st.error("Requests not available.")
        return

    backend = _get_backend_base()

    st.markdown("## History v2: Browse All Cases")
    st.caption("Browse all cases directly from S3 regardless of saved history.")

    # Fetch all case ids from S3
    cases: list[str] = []
    try:
        r = requests.get(f"{backend}/s3/cases", timeout=10)
        if r.ok:
            data = r.json() or {}
            cases = data.get("cases", []) or []
    except Exception:
        cases = []

    if not cases:
        st.info("No cases found in S3 bucket.")
        return

    # Build patient map (best-effort, cached)
    with st.spinner("Loading patient names…"):
        cid_to_patient = _case_to_patient_map(backend, cases)

    # Build display labels and predictive select
    def _label_for(cid: str) -> str:
        p = cid_to_patient.get(cid)
        return f"{cid} — {p}" if p else cid

    display_labels = [_label_for(cid) for cid in cases]
    label_to_cid = {lbl: cid for lbl, cid in zip(display_labels, cases)}

    st.markdown("<div style='height:.25rem'></div>", unsafe_allow_html=True)
    # Single list that shows all cases on click; built-in typeahead filters as you type
    sel_label = st.selectbox(
        "Search or select case (type case ID or patient name)",
        options=sorted(display_labels, key=lambda s: s.lower()),
        index=None,  # do not preselect; wait for user action
        placeholder="Start typing to filter, then pick a case",
        key="histv2_case_select_unified",
    )

    if not sel_label:
        st.info("Select a case to continue.")
        return

    case_id = label_to_cid.get(sel_label) or (sel_label.split("—", 1)[0].strip() if "—" in sel_label else sel_label.strip())
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

    # Fetch outputs (AI+Doctor) list under Output/
    outputs: list[dict] = []
    try:
        r = requests.get(f"{backend}/s3/{case_id}/outputs", timeout=10)
        if r.ok:
            data = r.json() or {}
            outputs = data.get("items", []) or []
    except Exception:
        outputs = []

    # Fetch ground truth assets
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

    # AI selector (dropdown)
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
        labels = [o.get("label") or (o.get("ai_key") or "").split("/")[-1] for o in outputs]
        selected_label = st.selectbox("Select AI output", options=labels or ["-"], index=0 if labels else 0, key="histv2_ai_label") if labels else None
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
    enable_sync = st.checkbox("Enable synchronized scrolling (Ground Truth ↔ AI Generated)", value=False, key="histv2_sync")
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


    # --- Discrepancy notes (History v2) ---
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
    n1, n2, n3 = st.columns([2, 2, 1])
    with n1:
        section_choice = st.selectbox("Section", options=section_options, index=0, key="histv2_disc_sec")
    with n2:
        subsections = toc_sections.get(section_choice, [])
        if subsections:
            subsection_choice = st.selectbox("Subsection", options=subsections, index=0, key="histv2_disc_sub")
        else:
            subsection_choice = st.text_input("Subsection (if none available)", value="", key="histv2_disc_sub_txt")
    with n3:
        severity = st.selectbox("Severity", options=["Low", "Medium", "High"], index=1, key="histv2_disc_sev")

    comment_text = st.text_area("Describe the discrepancy", key="histv2_disc_text")
    add_ok = st.button("Add comment", type="primary", key="histv2_add_btn")

    # Backend base
    backend = _get_backend_base()

    if add_ok and section_choice and comment_text:
        try:
            import requests as _rq
            sub = (subsection_choice.strip() if isinstance(subsection_choice, str) else subsection_choice) or (subsections[0] if subsections else section_choice)
            payload = {
                "case_id": case_id,
                "ai_label": selected_label or None,
                "section": section_choice,
                "subsection": sub,
                "username": current_user,
                "severity": severity,
                "comment": comment_text.strip(),
            }
            _rq.post(f"{backend}/comments", json=payload, timeout=8)
            st.success("Added.")
        except Exception:
            st.warning("Failed to add comment.")

    # List comments
    try:
        import requests as _rq
        params = {"ai_label": selected_label} if selected_label else None
        rcm = _rq.get(f"{backend}/comments/{case_id}", params=params, timeout=8)
        notes = rcm.json() if rcm.ok else []
    except Exception:
        notes = []

    if notes:
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        st.markdown("**Recorded comments**")
        h1, h2, h3, h4, h5, h6 = st.columns([1.0, 1.0, 0.7, 0.6, 2.0, 1.2])
        with h1: st.markdown("<div style='font-weight:700;'>Section</div>", unsafe_allow_html=True)
        with h2: st.markdown("<div style='font-weight:700;'>Subsection</div>", unsafe_allow_html=True)
        with h3: st.markdown("<div style='font-weight:700;'>User</div>", unsafe_allow_html=True)
        with h4: st.markdown("<div style='font-weight:700;'>Severity</div>", unsafe_allow_html=True)
        with h5: st.markdown("<div style='font-weight:700;'>When</div>", unsafe_allow_html=True)
        with h6: st.markdown("<div style='font-weight:700;'>Delete</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin-top:4px;margin-bottom:6px;opacity:.15;'>", unsafe_allow_html=True)
        for n in notes:
            is_resolved = bool(n.get("resolved"))
            row_style = "opacity:.85;background:rgba(255,255,255,0.03);border-radius:6px;padding:.2rem .35rem;" if is_resolved else ""
            text_style = "opacity:.7;color:#9aa0a6;" if is_resolved else ""
            st.markdown(f"<div style='{row_style}'></div>", unsafe_allow_html=True)
            c1, c2, c3, c4, c5, c6 = st.columns([1.0, 1.0, 0.7, 0.6, 2.0, 1.2])
            with c1:
                st.markdown(f"<div style='{text_style}'>{n.get('section') or '—'}</div>", unsafe_allow_html=True)
            with c2:
                sub = n.get("subsection") or (toc_sections.get(n.get("section") or "", [])[:1] or [n.get("section")])[0]
                st.markdown(f"<div style='{text_style}'>{sub or '—'}</div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div style='{text_style}'>{n.get('username') or 'anonymous'}</div>", unsafe_allow_html=True)
            with c4:
                st.markdown(f"<div style='{text_style}'>{n.get('severity') or '—'}</div>", unsafe_allow_html=True)
            with c5:
                when = (n.get("created_at") or "").replace("T", " ").replace("Z", " UTC")
                st.markdown(f"<div style='{text_style}'>{when or '—'}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{text_style};font-size:.85rem;opacity:.75;'>{n.get('comment') or ''}</div>", unsafe_allow_html=True)
            with c6:
                nid = n.get("id")
                cols_act = st.columns([0.6, 0.4])
                with cols_act[0]:
                    label = ("Resolve\u00A0\u00A0\u00A0" if not is_resolved else "Unresolve\u00A0\u00A0")
                    if nid and st.button(label, key=f"histv2_disc_res_{nid}"):
                        try:
                            _rq.patch(f"{backend}/comments/resolve", json={"id": int(nid), "case_id": case_id, "resolved": (not is_resolved)}, timeout=8)
                        except Exception:
                            pass
                        st.rerun()
                with cols_act[1]:
                    can_delete = (n.get("username") or "") == (st.session_state.get("username") or st.session_state.get("name") or "")
                    if nid and can_delete and st.button("Delete", key=f"histv2_disc_del_{nid}"):
                        try:
                            _rq.delete(f"{backend}/comments", json={"case_id": case_id, "ai_label": selected_label, "ids": [int(nid)]}, timeout=8)
                        except Exception:
                            pass
                        st.rerun()

if __name__ == "__main__":
    main()

