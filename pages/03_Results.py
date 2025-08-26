import streamlit as st
from datetime import datetime, timedelta
from app.ui import inject_base_styles, theme_provider
from pathlib import Path
import base64


def ensure_authenticated() -> bool:
    if st.session_state.get("authentication_status") is True:
        return True
    st.warning("Please login to access this page.")
    st.stop()


def header_actions(case_id: str) -> None:
    started = st.session_state.get("generation_start")
    ended = st.session_state.get("generation_end", datetime.now())
    if not started:
        started = ended
    elapsed_seconds = max(0, int((ended - started).total_seconds()))
    # Prefer computed processing seconds from generation page
    elapsed_seconds = st.session_state.get("processing_seconds", elapsed_seconds)
    elapsed_str = f"{elapsed_seconds // 60}m {elapsed_seconds % 60}s" if elapsed_seconds else "0s"
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;">
          <div style="display:flex;align-items:center;gap:.75rem;">
            <a href="#" style="text-decoration:none;opacity:.9;">← Back to Dashboard</a>
            <span style="opacity:.8;">Generated on {ended.strftime('%B %d, %Y at %I:%M %p').lstrip('0')}</span>
            <span style="opacity:.9;background:rgba(255,255,255,0.06);padding:.25rem .5rem;border:1px solid rgba(255,255,255,0.12);border-radius:10px;">Processing Complete</span>
          </div>
          <div style="display:flex;align-items:center;gap:.5rem;">
            <button disabled style="cursor:pointer;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.08);padding:.4rem .7rem;border-radius:8px;color:white;">Export All</button>
            <button disabled style="cursor:pointer;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.08);padding:.4rem .7rem;border-radius:8px;color:white;">Share</button>
          </div>
        </div>
        <h3 style="margin-top:.75rem;">Case ID: #{case_id} Results</h3>
        <div style="opacity:.85;margin-top:-6px;">Elapsed time: {elapsed_str}</div>
        """,
        unsafe_allow_html=True,
    )


def pdf_card(title: str, subtitle: str, pdf_path: Path | None) -> None:
    st.markdown(f"**{title}**")
    st.caption(subtitle)
    with st.container():
        st.markdown('<div class="section-bg">', unsafe_allow_html=True)
        if pdf_path and pdf_path.exists():
            with pdf_path.open("rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode("utf-8")
                st.markdown(
                    f"""
                    <iframe src="data:application/pdf;base64,{b64}" width="100%" height="520px" style="border:none;border-radius:10px;"></iframe>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("PDF not found.")
        st.markdown('</div>', unsafe_allow_html=True)


def summary_footer(rep_no: int | None = None) -> None:
    # Single Analysis Summary footer with accuracy, differences, and processing time
    # Processing time from session if available
    total_seconds = st.session_state.get("processing_seconds")
    if isinstance(total_seconds, int) and total_seconds >= 0:
        mm = total_seconds // 60
        ss = total_seconds % 60
        processing_display = f"{mm}m {ss}s"
    else:
        processing_display = "—"

    # Demo accuracy/differences vary deterministically by report number (newest is #1)
    if rep_no is None:
        accuracy = "—"
        differences = "—"
    else:
        accuracy = 95 - (rep_no % 8)
        differences = 10 + (rep_no % 12)

    st.markdown(
        f"""
        <div class="section-bg" style="margin-top:1rem;padding:.9rem 1.1rem;">
          <div style="font-weight:700;margin-bottom:.35rem;">Analysis Summary</div>
          <div style="display:flex;align-items:center;justify-content:space-around;gap:1rem;text-align:center;">
            <div>
              <div style="font-weight:700;font-size:1.15rem;">{accuracy}%</div>
              <div style="opacity:.8;">Accuracy Score</div>
            </div>
            <div>
              <div style="font-weight:700;font-size:1.15rem;">{differences}</div>
              <div style="opacity:.8;">Key Differences</div>
            </div>
            <div>
              <div style="font-weight:700;font-size:1.15rem;">{processing_display}</div>
              <div style="opacity:.8;">Processing Time</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Results", page_icon="📑", layout="wide")
    theme_provider()
    inject_base_styles()
    ensure_authenticated()

    case_id = st.session_state.get("last_case_id", "0000")
    # no report_id anymore

    # Discover all PDFs and paginate: newest first, 3 per page mapped to the three cards
    results_dir = Path("results")
    all_pdfs = []
    if results_dir.exists():
        all_pdfs = sorted(results_dir.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)

    # Demo: ensure multiple pages exist by padding with placeholders
    MIN_REPORTS_DEMO = 9  # 3 pages x 3 cards
    if len(all_pdfs) < MIN_REPORTS_DEMO:
        all_pdfs = all_pdfs + [None] * (MIN_REPORTS_DEMO - len(all_pdfs))

    # Page index via query param `p` (1-based for display)
    qp = st.experimental_get_query_params() or {}
    try:
        current_page = max(1, int(qp.get("p", ["1"])[0]))
    except Exception:
        current_page = 1

    page_size = 3
    total_pages = max(1, (len(all_pdfs) + page_size - 1) // page_size)
    if current_page > total_pages:
        current_page = total_pages

    # Override displayed Case ID for demo pages 2 and 3
    display_case_id = case_id
    if current_page == 2:
        display_case_id = "1042"
    elif current_page == 3:
        display_case_id = "1111"

    # Header now that we know the page and display id
    header_actions(display_case_id)

    start_idx = (current_page - 1) * page_size
    page_items = all_pdfs[start_idx:start_idx + page_size]

    # Report numbers: 1 is newest overall
    def report_number_from_index(global_index: int) -> int:
        return global_index + 1

    # Assign to cards
    items_with_labels = [
        ("Ground Truth", "Original reference document"),
        ("Generated Report", "AI-generated analysis report"),
        ("Comparison Report", "Detailed comparison analysis"),
    ]
    cols = st.columns(3)
    for idx, col in enumerate(cols):
        with col:
            pdf_path = page_items[idx] if idx < len(page_items) else None
            if pdf_path is not None:
                global_idx = start_idx + idx
                rep_no = report_number_from_index(global_idx)
                title, subtitle = items_with_labels[idx]
                pdf_card(f"{title} • Report #{rep_no}", subtitle, pdf_path)
            else:
                title, subtitle = items_with_labels[idx]
                pdf_card(title, subtitle, None)

    # Pager controls
    prev_col, info_col, next_col = st.columns([1, 2, 1])
    with prev_col:
        if current_page > 1 and st.button("← Newer", key="pager_prev"):
            st.experimental_set_query_params(p=str(current_page - 1))
            st.experimental_rerun()
    with info_col:
        st.markdown(f"<div style='text-align:center;opacity:.85;'>Page {current_page} of {total_pages}</div>", unsafe_allow_html=True)
    with next_col:
        if current_page < total_pages and st.button("Older →", key="pager_next"):
            st.experimental_set_query_params(p=str(current_page + 1))
            st.experimental_rerun()

    # Footer reflects the most recent report number shown in the first card of the page
    first_rep_no = start_idx + 1 if page_items else None
    summary_footer(first_rep_no)


main()


