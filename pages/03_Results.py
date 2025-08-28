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


def display_pdf_column(title: str, subtitle: str, pdf_data: str = None, pdf_key: str = None, s3_manager=None) -> None:
    """Display a PDF column with title, subtitle, and PDF content"""
    st.markdown(f"**{title}**")
    st.caption(subtitle)
    
    with st.container():
        # st.markdown('<div class="section-bg">', unsafe_allow_html=True)
        
        if pdf_data:
            # Display PDF from base64 data
            st.markdown(
                f"""
                <iframe src="data:application/pdf;base64,{pdf_data}" 
                        width="100%" height="520px" 
                        style="border:none;border-radius:10px;"></iframe>
                """,
                unsafe_allow_html=True,
            )
        elif pdf_key and s3_manager:
            # Try to fetch from S3
            pdf_data = s3_manager.get_pdf_base64(pdf_key)
            if pdf_data:
                st.markdown(
                    f"""
                    <iframe src="data:application/pdf;base64,{pdf_data}" 
                            width="100%" height="520px" 
                            style="border:none;border-radius:10px;"></iframe>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.info("PDF not available from S3.")
        else:
            st.info("PDF not available.")
            
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
    
    # Get comparison reports for dropdown
    comparison_reports = []
    if s3_manager.s3_client:
        comparison_reports = s3_manager.get_comparison_reports(case_id)
    else:
        # Mock comparison reports
        comparison_reports = [
            {"key": f"case_{case_id}/comparison/report_v1.pdf", "filename": "Report v1", "size": 1024000},
            {"key": f"case_{case_id}/comparison/report_v2.pdf", "filename": "Report v2", "size": 1024000},
            {"key": f"case_{case_id}/comparison/report_v3.pdf", "filename": "Report v3", "size": 1024000},
        ]
    
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
        display_pdf_column(
            title="Ground Truth",
            subtitle="Original document for comparison",
            pdf_key=ground_truth_key,
            s3_manager=s3_manager
        )
    
    with col2:
        # Complete Generated Report PDF
        complete_report_key = case_files.get('complete_report')
        if complete_report_key:
            display_pdf_column(
                title="Complete AI Generated Report",
                subtitle="All sections combined from n8n workflow",
                pdf_key=complete_report_key,
                s3_manager=s3_manager
            )
        else:
            # Fallback to individual sections
            st.markdown("**AI Generated Report Sections**")
            st.caption("Individual sections generated by n8n workflow")
            
            output_reports = case_files.get('output_reports', [])
            if output_reports:
                # Show sections in a dropdown
                section_options = []
                for report in output_reports:
                    # Extract section name from filename
                    filename = report.split('/')[-1]
                    if 'section' in filename.lower():
                        section_num = filename.split('section_')[1].split('_')[0] if 'section_' in filename.lower() else 'Unknown'
                        section_options.append(f"Section {section_num}")
                    else:
                        section_options.append(filename.replace('.pdf', ''))
                
                section_options.insert(0, "Select a section...")
                
                selected_section = st.selectbox(
                    "Choose section to view:",
                    options=section_options,
                    key="section_dropdown"
                )
                
                if selected_section and selected_section != "Select a section...":
                    section_idx = section_options.index(selected_section) - 1
                    section_key = output_reports[section_idx]
                    
                    with st.container():
                        # st.markdown('<div class="section-bg">', unsafe_allow_html=True)
                        pdf_data = s3_manager.get_pdf_base64(section_key) if s3_manager.s3_client else None
                        if pdf_data:
                            st.markdown(
                                f"""
                                <iframe src="data:application/pdf;base64,{pdf_data}" 
                                        width="100%" height="520px" 
                                        style="border:none;border-radius:10px;"></iframe>
                                """,
                                unsafe_allow_html=True,
                            )
                        else:
                            st.info("PDF not available.")
                        st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info("Please select a section from the dropdown above.")
            else:
                st.info("No generated sections available yet.")
    
    with col3:
        # Input Files (fed to LLM)
        st.markdown("**Input Files**")
        st.caption("Documents fed to LLM via n8n workflow")
        
        input_files = case_files.get('input_files', [])
        if input_files:
            # Show input files in a dropdown
            input_options = []
            for input_file in input_files:
                filename = input_file.split('/')[-1]
                input_options.append(filename)
            
            input_options.insert(0, "Select an input file...")
            
            selected_input = st.selectbox(
                "Choose input file to view:",
                options=input_options,
                key="input_dropdown"
            )
            
            if selected_input and selected_input != "Select an input file...":
                # Find the selected input file
                selected_idx = input_options.index(selected_input) - 1
                input_key = input_files[selected_idx]
                
                # Display the selected input PDF
                with st.container():
                    # st.markdown('<div class="section-bg">', unsafe_allow_html=True)
                    pdf_data = s3_manager.get_pdf_base64(input_key) if s3_manager.s3_client else None
                    if pdf_data:
                        st.markdown(
                            f"""
                            <iframe src="data:application/pdf;base64,{pdf_data}" 
                                    width="100%" height="520px" 
                                    style="border:none;border-radius:10px;"></iframe>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info("PDF not available.")
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("Please select an input file from the dropdown above.")
        else:
            st.info("No input files available.")
    
    # Summary footer
    summary_footer(1)
    
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
            
        complete_report = case_files.get('complete_report')
        output_sections = case_files.get('output_reports', [])
        input_files = case_files.get('input_files', [])
        
        if complete_report:
            st.markdown(f"- ✅ Complete Report: Available")
        elif output_sections:
            st.markdown(f"- ✅ Generated Sections: {len(output_sections)} available")
        else:
            st.markdown("- ❌ Generated Reports: Not found")
            
        st.markdown(f"- 📄 Input Files: {len(input_files)} available")
        
        # Show metadata files
        metadata_files = case_files.get('metadata', {})
        if metadata_files:
            st.markdown(f"- 📋 Metadata Files: {len(metadata_files)} available")
    
    # S3 connection status
    if not s3_manager.s3_client:
        st.warning(
            "⚠️ **Demo Mode**: S3 connection not available. "
            "Displaying mock data. To connect to real S3, set environment variables: "
            "`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`"
        )


if __name__ == "__main__":
    main()


