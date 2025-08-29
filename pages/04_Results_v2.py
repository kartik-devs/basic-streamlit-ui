import streamlit as st
from datetime import datetime
from app.ui import inject_base_styles, theme_provider
import os


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


def main() -> None:
    st.set_page_config(page_title="Results v2", page_icon="🧪", layout="wide")
    theme_provider()
    inject_base_styles()

    case_id = (
        st.session_state.get("last_case_id")
        or st.session_state.get("current_case_id")
        or _qp_get("case_id", "0000")
    )
    backend = _get_backend_base()

    # Attempt to compute patient name from assets later
    st.markdown("## Results v2")
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
        st.markdown('<div style="height:85px"></div>', unsafe_allow_html=True)
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
        st.markdown('<div style="height:85px"></div>', unsafe_allow_html=True)
        doc_area = st.empty()

    # Fetch ground truth separately using existing assets endpoint (latest)
    assets = {}
    gt_pdf = None
    gt_generic = None
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
    if sel_ai and sel_ai.get("ai_url"):
        with col2:
            _iframe(sel_ai["ai_url"])
    else:
        with col2:
            st.info("Not available")

    doc_pdf = sel_ai.get("doctor_url") if sel_ai else None
    if doc_pdf:
        with col3:
            _iframe(doc_pdf)
    else:
        with col3:
            st.info("Not available")


if __name__ == "__main__":
    main()


