import streamlit as st
import requests
import os
from datetime import datetime
from typing import List, Dict, Any
import re

# Import UI components
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.ui import inject_base_styles, show_header
from app.auth import require_authentication, get_current_user, logout

# Require authentication for this page
require_authentication()


def _get_backend_base() -> str:
    """Get backend base URL from environment or query params."""
    params = st.query_params if hasattr(st, "query_params") else {}
    return (
        (params.get("api", [None])[0] if isinstance(params.get("api"), list) else params.get("api"))
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
    ).rstrip("/")


def get_case_report(case_id: str) -> Dict[str, Any]:
    """Fetch the deposition report HTML for a case from S3"""
    try:
        backend = _get_backend_base()
        response = requests.get(f"{backend}/s3/case/{case_id}/report", timeout=30)
        if response.ok:
            return response.json()
        else:
            return {"error": f"Failed to fetch report: {response.status_code}"}
    except Exception as e:
        return {"error": f"Error connecting to backend: {str(e)}"}


def group_documents_by_provider(documents: List[Dict]) -> Dict[str, List[Dict]]:
    """Group documents by provider/source"""
    grouped = {}
    for doc in documents:
        # Extract provider from filename
        filename = doc.get("filename", "")
        provider = "Unknown Provider"
        
        # Common patterns in filenames
        if "__grp-" in filename:
            # Format: all_00001__grp-14. Spot PT__src-...
            match = re.search(r"__grp-(.+?)__src", filename)
            if match:
                provider = match.group(1).strip()
        
        if provider not in grouped:
            grouped[provider] = []
        grouped[provider].append(doc)
    
    return grouped


def main():
    st.set_page_config(
        page_title="Deposition Report",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    inject_base_styles()
    show_header(
        title="Deposition Report",
        subtitle="View Medical Deposition Report with Source Links",
        icon="📄",
    )
    
    # Get case ID from query params or user input
    query_params = st.query_params if hasattr(st, "query_params") else {}
    default_case_id = query_params.get("case", [""])[0] if isinstance(query_params.get("case"), list) else query_params.get("case", "")
    
    # Case ID input
    col1, col2 = st.columns([3, 1])
    with col1:
        case_id = st.text_input(
            "Enter Case ID",
            value=default_case_id,
            placeholder="e.g., 4890",
            help="Enter the 4-digit case ID to view the deposition report"
        )
    
    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        load_btn = st.button("🔍 Load Report", type="primary", use_container_width=True)
    
    if not case_id:
        st.info("👆 Enter a Case ID to view the deposition report")
        
        # Show example/instructions
        st.markdown("""
        ### 📚 How to Use
        
        1. **Enter Case ID:** Type the 4-digit case ID in the box above
        2. **Load Report:** Click the "Load Report" button
        3. **View Report:** The deposition report will be displayed below
        4. **Click Source Links:** Click any source citation to view the original document
        
        ---
        
        ### 🎯 Features
        
        - **Full Report View:** Complete deposition report with all sections
        - **Source Links:** Click citations to view original source documents
        - **Direct S3 Access:** All source files open directly from S3
        - **Download:** Download the full report or individual sources
        """)
        return
    
    if load_btn or default_case_id:
        with st.spinner(f"Loading report for Case {case_id}..."):
            result = get_case_report(case_id)
        
        if "error" in result:
            st.error(f"❌ {result['error']}")
            st.info("Make sure the report HTML is uploaded to S3 at: `{case_id}/Output/deposition_report.html`")
            return
        
        report_url = result.get("report_url")
        report_html = result.get("report_html")
        
        if not report_url and not report_html:
            st.warning(f"No deposition report found for Case {case_id}")
            st.info("Upload the report to S3 at: `{case_id}/Output/deposition_report.html`")
            return
        
        # Success message
        st.success(f"✅ Loaded deposition report for Case {case_id}")
        
        # Download button
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if report_url:
                st.link_button("⬇️ Download Report", report_url, use_container_width=True)
        
        # Display the HTML report
        st.markdown("---")
        
        if report_html:
            # Display HTML content directly with iframe
            st.components.v1.html(report_html, height=800, scrolling=True)
        elif report_url:
            # Display using iframe with presigned URL
            st.markdown(f"""
            <iframe src="{report_url}" width="100%" height="800px" style="border: 1px solid #ddd; border-radius: 8px;"></iframe>
            """, unsafe_allow_html=True)


def display_grid_view(documents: List[Dict]):
    """Display documents in grid view with thumbnails"""
    # Create grid layout
    cols_per_row = 3
    
    for i in range(0, len(documents), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j, doc in enumerate(documents[i:i+cols_per_row]):
            with cols[j]:
                display_document_card(doc)


def display_list_view(documents: List[Dict]):
    """Display documents in list view"""
    for doc in documents:
        display_document_row(doc)


def display_document_card(doc: Dict):
    """Display a single document as a card"""
    filename = doc.get("filename", "Unknown")
    url = doc.get("url", "")
    size = doc.get("size", 0)
    modified = doc.get("last_modified", "")
    
    # Extract display name
    display_name = filename.split("__src-")[-1] if "__src-" in filename else filename
    display_name = display_name.replace(".png", "").replace("_", " ")
    
    # Card container
    with st.container():
        st.markdown(f"""
        <div style="
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 12px;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            height: 100%;
        ">
            <div style="
                background: #f5f5f5;
                height: 150px;
                border-radius: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 8px;
            ">
                <span style="font-size: 48px;">📄</span>
            </div>
            <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                {display_name[:30]}...
            </div>
            <div style="color: #666; font-size: 12px;">
                {format_file_size(size)}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👁️ View", key=f"view_{filename}", use_container_width=True):
                st.session_state[f"viewing_{filename}"] = True
        with col2:
            st.link_button("⬇️ Download", url, use_container_width=True)
        
        # Show image in modal/expander if viewing
        if st.session_state.get(f"viewing_{filename}"):
            with st.expander("🖼️ Image Viewer", expanded=True):
                st.image(url, use_column_width=True)
                if st.button("Close", key=f"close_{filename}"):
                    st.session_state[f"viewing_{filename}"] = False
                    st.rerun()


def display_document_row(doc: Dict):
    """Display a single document as a list row"""
    filename = doc.get("filename", "Unknown")
    url = doc.get("url", "")
    size = doc.get("size", 0)
    modified = doc.get("last_modified", "")
    
    # Extract display info
    display_name = filename.split("__src-")[-1] if "__src-" in filename else filename
    provider = ""
    if "__grp-" in filename:
        match = re.search(r"__grp-(.+?)__src", filename)
        if match:
            provider = match.group(1).strip()
    
    # Row container
    col1, col2, col3, col4, col5 = st.columns([0.5, 3, 2, 1, 1.5])
    
    with col1:
        st.markdown("📄")
    
    with col2:
        st.markdown(f"**{display_name}**")
    
    with col3:
        if provider:
            st.markdown(f"<small>{provider}</small>", unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"<small>{format_file_size(size)}</small>", unsafe_allow_html=True)
    
    with col5:
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("👁️", key=f"view_{filename}", help="View"):
                st.session_state[f"viewing_{filename}"] = True
        with btn_col2:
            st.link_button("⬇️", url, help="Download")
    
    # Show image in expander if viewing
    if st.session_state.get(f"viewing_{filename}"):
        with st.expander("🖼️ Image Viewer", expanded=True):
            st.image(url, use_column_width=True)
            if st.button("Close", key=f"close_{filename}"):
                st.session_state[f"viewing_{filename}"] = False
                st.rerun()
    
    st.markdown("---")


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


if __name__ == "__main__":
    main()
