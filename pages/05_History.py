import streamlit as st
from app.ui import inject_base_styles, theme_provider
import os


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
        st.info("No saved cases yet. Open Results v2 and click ‘Save to history’.")
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

    # Ground Truth (left)
    gt_url = None
    for it in items:
        gk = it.get("ground_truth_key")
        if gk:
            try:
                pr = requests.get(f"{backend}/s3/ensure-pdf", params={"key": gk}, timeout=10)
                if pr.ok:
                    gt_url = (pr.json() or {}).get("url")
                    break
            except Exception:
                continue
    with col1:
        st.markdown("**Ground Truth**")
        st.markdown('<div style="height:85px"></div>', unsafe_allow_html=True)
        if gt_url and gt_url.lower().split('?',1)[0].endswith('.pdf'):
            st.markdown(f"<iframe src=\"{gt_url}\" width=\"100%\" height=\"520\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
        elif gt_url:
            st.markdown(f"<a href=\"{gt_url}\" class=\"st-a\" target=\"_blank\">📄 Download Ground Truth</a>", unsafe_allow_html=True)
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
        if ai_url:
            st.markdown(f"<iframe src=\"{ai_url}\" width=\"100%\" height=\"520\" style=\"border:none;border-radius:10px;\"></iframe>", unsafe_allow_html=True)
        else:
            st.info("Not available")

    # Doctor (right) matching selected AI
    with col3:
        st.markdown("**Doctor as LLM**")
        st.markdown('<div style="height:85px"></div>', unsafe_allow_html=True)
        # Show patient name parsed from saved labels/keys
        try:
            from pages import _04_Results_v2 as results_v2  # type: ignore
            _extract = getattr(results_v2, "_extract_patient_from_strings", None)
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


if __name__ == "__main__":
    main()


