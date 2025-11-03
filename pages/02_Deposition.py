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


def _get_backend_base() -> str:
    """Get backend base URL from environment or query params."""
    params = st.query_params if hasattr(st, "query_params") else {}
    return (
        (params.get("api", [None])[0] if isinstance(params.get("api"), list) else params.get("api"))
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
    ).rstrip("/")


def get_case_documents(case_id: str) -> Dict[str, Any]:
    """Fetch all documents for a case from S3"""
    try:
        backend = _get_backend_base()
        response = requests.get(f"{backend}/s3/case/{case_id}/documents", timeout=30)
        if response.ok:
            return response.json()
        else:
            return {"error": f"Failed to fetch documents: {response.status_code}"}
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
        page_title="Deposition Documents",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    inject_base_styles()
    show_header(
        title="Deposition Documents",
        subtitle="View and Download Source Documents",
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
            help="Enter the 4-digit case ID to view documents"
        )
    
    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        load_btn = st.button("🔍 Load Documents", type="primary", use_container_width=True)
    
    if not case_id:
        st.info("👆 Enter a Case ID to view documents")
        
        # Show example/instructions
        st.markdown("""
        ### 📚 How to Use
        
        1. **Enter Case ID:** Type the 4-digit case ID in the box above
        2. **Load Documents:** Click the "Load Documents" button
        3. **Browse:** View documents organized by provider
        4. **Filter:** Use search and filter options
        5. **View/Download:** Click on any document to view or download
        
        ---
        
        ### 🎯 Features
        
        - **Organized View:** Documents grouped by provider
        - **Search:** Find specific documents quickly
        - **Direct Access:** All S3 images available with fresh presigned URLs
        - **Download:** Bulk download or individual files
        - **Image Viewer:** Built-in image viewer with zoom
        """)
        return
    
    if load_btn or default_case_id:
        with st.spinner(f"Loading documents for Case {case_id}..."):
            result = get_case_documents(case_id)
        
        if "error" in result:
            st.error(f"❌ {result['error']}")
            return
        
        documents = result.get("documents", [])
        
        if not documents:
            st.warning(f"No documents found for Case {case_id}")
            return
        
        # Success message
        st.success(f"✅ Found {len(documents)} documents for Case {case_id}")
        
        # Filter and search options
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            search_term = st.text_input(
                "🔍 Search documents",
                placeholder="Search by filename, provider, or date...",
                label_visibility="collapsed"
            )
        
        with col2:
            # Get unique providers
            grouped = group_documents_by_provider(documents)
            providers = ["All Providers"] + sorted(grouped.keys())
            selected_provider = st.selectbox(
                "Filter by Provider",
                providers,
                label_visibility="collapsed"
            )
        
        with col3:
            view_mode = st.radio(
                "View",
                ["Grid", "List"],
                horizontal=True,
                label_visibility="collapsed"
            )
        
        # Filter documents
        filtered_docs = documents
        if search_term:
            filtered_docs = [
                doc for doc in documents
                if search_term.lower() in doc.get("filename", "").lower()
            ]
        
        if selected_provider != "All Providers":
            filtered_docs = grouped.get(selected_provider, [])
        
        st.markdown(f"**Showing {len(filtered_docs)} of {len(documents)} documents**")
        
        # Display documents
        if view_mode == "Grid":
            display_grid_view(filtered_docs)
        else:
            display_list_view(filtered_docs)


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
