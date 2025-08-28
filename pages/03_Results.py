import streamlit as st
st.set_page_config(page_title="Results", page_icon="📑", layout="wide")

from datetime import datetime, timedelta
from app.ui import inject_base_styles, theme_provider
from app.s3_utils import get_s3_manager, mock_s3_data_for_demo
from pathlib import Path
import base64
import os
import requests


def ensure_authenticated() -> bool:
    # Check multiple possible authentication indicators
    auth_status = st.session_state.get("authentication_status")
    name = st.session_state.get("name")
    username = st.session_state.get("username")
    
    # Debug info (remove this after fixing)
    st.write("🔍 Debug - Session State Keys:", list(st.session_state.keys()))
    st.write("🔍 Debug - Auth Status:", auth_status)
    st.write("🔍 Debug - Name:", name)
    st.write("🔍 Debug - Username:", username)
    
    # Check if user is authenticated (multiple indicators)
    if (auth_status is True) or (name is not None) or (username is not None):
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


def display_file_column(title: str, subtitle: str, file_data: str = None, file_key: str = None, s3_manager=None) -> None:
    """Display a file column with title, subtitle, and file content (PDF or Word)"""
    st.markdown(f"**{title}**")
    st.caption(subtitle)
    
    with st.container():
        # st.markdown('<div class="section-bg">', unsafe_allow_html=True)
        
        if file_data:
            # Display file from base64 data
            if file_key and file_key.lower().endswith('.docx'):
                # For Word documents, show download link and preview info
                st.success("📄 Word Document Available")
                st.info("Word documents (.docx) cannot be previewed directly in the browser.")
                st.markdown("**File Details:**")
                st.markdown(f"- **Filename:** {file_key.split('/')[-1]}")
                st.markdown(f"- **Type:** Microsoft Word Document")
                st.markdown(f"- **Size:** {len(file_data)} bytes")
                
                # Create a download button
                st.download_button(
                    label="📥 Download Word Document",
                    data=file_data,
                    file_name=file_key.split('/')[-1],
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                # For PDFs, show in iframe
                st.markdown(
                    f"""
                    <iframe src="data:application/pdf;base64,{file_data}" 
                            width="100%" height="520px" 
                            style="border:none;border-radius:10px;"></iframe>
                    """,
                    unsafe_allow_html=True,
                )
        elif file_key and s3_manager:
            # Try to fetch from S3
            file_data = s3_manager.get_file_base64(file_key)
            if file_data:
                if file_key.lower().endswith('.docx'):
                    # For Word documents, show download link and preview info
                    st.success("📄 Word Document Available")
                    st.info("Word documents (.docx) cannot be previewed directly in the browser.")
                    st.markdown("**File Details:**")
                    st.markdown(f"- **Filename:** {file_key.split('/')[-1]}")
                    st.markdown(f"- **Type:** Microsoft Word Document")
                    st.markdown(f"- **Size:** {len(file_data)} bytes")
                    
                    # Create a download button
                    st.download_button(
                        label="📥 Download Word Document",
                        data=file_data,
                        file_name=file_key.split('/')[-1],
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    # For PDFs, show in iframe
                    st.markdown(
                        f"""
                        <iframe src="data:application/pdf;base64,{file_data}" 
                                width="100%" height="520px" 
                                style="border:none;border-radius:10px;"></iframe>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.info("File not available from S3.")
        else:
            st.info("File not available.")
            
        st.markdown('</div>', unsafe_allow_html=True)


def summary_footer(rep_no: int | None = None) -> None:
    """Display analysis summary footer with accuracy, differences, and processing time"""
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
    theme_provider()
    inject_base_styles()
    ensure_authenticated()

    # Get case ID from session or query params
    case_id = (st.session_state.get("last_case_id") or 
               st.session_state.get("current_case_id") or 
               "0000")
    
    # Initialize S3 manager
    s3_manager = get_s3_manager()
    
    # Get case files from S3 (or mock data if S3 not available)
    if s3_manager.s3_client:
        case_files = s3_manager.get_case_files(case_id)
    else:
        # Use mock data for demo purposes
        case_files = mock_s3_data_for_demo(case_id)
    

    
    # Header section
    header_actions(case_id)
    
    # Main content - Three PDFs side by side
    st.markdown("## Report Comparison")
    st.markdown("Compare the ground truth, generated report, and historical reports side by side.")
    
    # Create three columns for PDFs
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Ground Truth PDF
        ground_truth_key = case_files.get('ground_truth')
        display_file_column(
            title="Ground Truth",
            subtitle="Original document for comparison",
            file_key=ground_truth_key,
            s3_manager=s3_manager
        )
    
    with col2:
        # AI Generated Report (from n8n workflow)
        ai_report_key = case_files.get('ai_generated_report')
        if ai_report_key:
            display_file_column(
                title="AI Generated Report",
                subtitle="Output from n8n workflow",
                file_key=ai_report_key,
                s3_manager=s3_manager
            )
        else:
            st.info("AI Generated Report not available yet. The n8n workflow may still be processing.")
    
    with col3:
        # Doctor/LLM Reports (previous versions for comparison)
        doctor_reports = case_files.get('doctor_reports', [])
        if doctor_reports:
            # Show doctor reports in a dropdown
            report_options = []
            for report in doctor_reports:
                filename = report.split('/')[-1]
                report_options.append(filename)
            
            report_options.insert(0, "Select a report to compare...")
            
            selected_report = st.selectbox(
                "Doctor/LLM Reports:",
                options=report_options,
                key="doctor_report_dropdown"
            )
            
            if selected_report and selected_report != "Select a report to compare...":
                # Find the selected report
                selected_idx = report_options.index(selected_report) - 1
                report_key = doctor_reports[selected_idx]
                
                # Display the selected report directly without extra spacing
                file_data = s3_manager.get_file_base64(report_key) if s3_manager.s3_client else None
                if file_data:
                    st.markdown(
                        f"""
                        <iframe src="data:application/pdf;base64,{file_data}" 
                                width="100%" height="520px" 
                                style="border:none;border-radius:10px;"></iframe>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("PDF not available.")
            else:
                st.info("Please select a report from the dropdown above.")
        else:
            st.info("No doctor/LLM reports available for comparison.")
    

    
    # Additional information section
    st.markdown("---")
    st.markdown("## Report Details")
    
    # Display case information
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.markdown("**Case Information**")
        st.markdown(f"- **Case ID:** {case_id}")
        st.markdown(f"- **Status:** Completed")
        st.markdown(f"- **Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        
        if s3_manager.s3_client:
            st.markdown(f"- **Storage:** S3 Bucket: {s3_manager.bucket_name}")
        else:
            st.markdown("- **Storage:** Demo Mode (Mock Data)")
    
    with col_info2:
        st.markdown("**Available Files**")
        if case_files.get('ground_truth'):
            st.markdown(f"- ✅ Ground Truth: Available")
        else:
            st.markdown("- ❌ Ground Truth: Not found")
            
        ai_report = case_files.get('ai_generated_report')
        
        if ai_report:
            st.markdown(f"- ✅ AI Generated Report: Available")
        else:
            st.markdown("- ❌ AI Generated Report: Not found")
            
        doctor_reports = case_files.get('doctor_reports', [])
        if doctor_reports:
            st.markdown(f"- ✅ Doctor/LLM Reports: {len(doctor_reports)} available")
        else:
            st.markdown("- ❌ Doctor/LLM Reports: Not found")
    
    # S3 connection status
    if not s3_manager.s3_client:
        st.warning(
            "⚠️ **Demo Mode**: S3 connection not available. "
            "Displaying mock data. To connect to real S3, set environment variables: "
            "`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`"
        )


if __name__ == "__main__":
    main()


