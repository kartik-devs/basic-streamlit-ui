import streamlit as st
from streamlit_extras.switch_page_button import switch_page
import os
from dotenv import load_dotenv
import requests
import time

# Local modules
from app.ui import inject_base_styles, show_header
from app.auth import is_authenticated, show_login_page, get_current_user, logout

# --- CONFIGURATION ---
BACKEND_URL = "https://basic-streamlit-ui.onrender.com"  

# =========================================================
# 🔒 SECURE DOCUMENT GATEKEEPER
# =========================================================
query_params = st.query_params
doc_id = query_params.get("doc_id", None)

if doc_id:
    st.set_page_config(page_title="Secure Evidence Viewer", layout="centered")
    
    st.title("🔒 Secure Evidence Gateway")
    st.info(f"Requesting Evidence File: **{doc_id}**")
    st.markdown("---")

    # 1. We need the Case ID to find the correct folder in S3
    case_id_input = st.text_input("Enter Case ID (e.g., 4788):")
    
    # 2. Access Code
    password = st.text_input("Enter Access Code:", type="password")
    
    if st.button("Authenticate & View"):
        if password == "legal2025":  
            if not case_id_input:
                st.error("⚠️ Please enter the Case ID.")
                st.stop()

            with st.spinner("Locating evidence file..."):
                time.sleep(1) 
                
                # --- NEW LOGIC: Fetch Evidence (Input) Documents ---
                try:
                    # We use the endpoint that lists ALL input pages for a case
                    api_url = f"{BACKEND_URL}/s3/case/{case_id_input}/documents"
                    response = requests.get(api_url, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        documents = data.get("documents", [])
                        
                        # Find the specific file that matches 'doc_id'
                        target_file = None
                        
                        # Loose matching: check if doc_id is inside the filename
                        for doc in documents:
                            if doc_id in doc.get("filename", ""):
                                target_file = doc
                                break
                        
                        # If not found, just default to the first document or show error
                        if not target_file and documents:
                            st.warning(f"File '{doc_id}' not explicitly found in Case {case_id_input}. Showing first available document.")
                            target_file = documents[0]

                        if target_file:
                            file_url = target_file.get("url")
                            st.success("Access Granted.")
                            
                            # Display
                            if ".pdf" in target_file.get("filename", "").lower():
                                st.markdown(f'<iframe src="{file_url}" width="100%" height="800px" style="border:none;"></iframe>', unsafe_allow_html=True)
                            else:
                                st.image(file_url, caption=f"Evidence: {target_file['filename']}", use_container_width=True)
                                
                            st.warning("⚠️ CONFIDENTIAL: Access logged. Do not distribute.")
                        else:
                            st.error(f"❌ No documents found in Case {case_id_input}. Check the Case ID.")
                    else:
                        st.error(f"Server Error: Backend returned status {response.status_code}")
                        
                except Exception as e:
                    st.error(f"❌ Connection Error: {e}")

        elif password:
            st.error("⛔ Access Denied: Invalid Credentials")
            
    # Return Button
    st.markdown("---")
    if st.button("Return to Dashboard"):
        st.query_params.clear()
        st.rerun()

    st.stop()


# =========================================================
# 🏠 NORMAL MAIN APPLICATION
# =========================================================
def main() -> None:
    # Check authentication first
    if not is_authenticated():
        show_login_page()
        return
    
    # Standard Dashboard Config
    st.set_page_config(
        page_title="CaseTracker Pro",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    inject_base_styles()
    
    # Add logout button in sidebar
    with st.sidebar:
        user = get_current_user()
        if user:
            st.markdown(f"**👤 {user['name']}**")
            st.markdown(f"_{user['email']}_")
            st.markdown("---")
            if st.button("🚪 Logout", use_container_width=True):
                logout()
                st.rerun()
    
    show_header(
        title="CaseTracker Pro",
        subtitle="Medical Report Generation System",
        icon="📋",
    )

    # Welcome message
    st.markdown("""
    <div style="text-align: center; margin: 2rem 0;">
        <h2 style="color: #3b82f6; margin-bottom: 1rem;">Welcome to CaseTracker Pro</h2>
        <p style="color: #6b7280; font-size: 1.1rem; margin-bottom: 2rem;">
            Generate comprehensive medical reports with AI-powered analysis.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Navigation buttons
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        if st.button("📋 Case Report", type="primary", use_container_width=True):
            try:
                from streamlit_extras.switch_page_button import switch_page
                for name in ["01_Case_Report", "Case Report", "01 Case Report", "Case_Report"]:
                    try:
                        switch_page(name)
                        return
                    except Exception:
                        continue
            except Exception:
                st.info("Please use the sidebar to navigate to Case Report.")
    
    with col2:
        if st.button("📄 Deposition", use_container_width=True):
            try:
                from streamlit_extras.switch_page_button import switch_page
                for name in ["02_Deposition", "Deposition", "02 Deposition", "Deposition Page"]:
                    try:
                        switch_page(name)
                        return
                    except Exception:
                        continue
            except Exception:
                st.info("Please use the sidebar to navigate to Deposition.")
    
    with col3:
        if st.button("📊 Results", use_container_width=True):
            try:
                from streamlit_extras.switch_page_button import switch_page
                for name in ["04_Results", "Results", "04 Results", "Results Page"]:
                    try:
                        switch_page(name)
                        return
                    except Exception:
                        continue
            except Exception:
                st.info("Please use the sidebar to navigate to Results.")
    
    with col4:
        if st.button("📚 History", use_container_width=True):
            try:
                from streamlit_extras.switch_page_button import switch_page
                for name in ["05_History", "History", "05 History", "History Page"]:
                    try:
                        switch_page(name)
                        return
                    except Exception:
                        continue
            except Exception:
                st.info("Please use the sidebar to navigate to History.")
    
    with col5:
        if st.button("🔄 Version Compare", use_container_width=True):
            try:
                from streamlit_extras.switch_page_button import switch_page
                for name in ["06_Version_Comparison", "Version Comparison", "06 Version Comparison", "Version_Comparison"]:
                    try:
                        switch_page(name)
                        return
                    except Exception:
                        continue
            except Exception:
                st.info("Please use the sidebar to navigate to Version Comparison.")
    
    with col6:
        if st.button("ℹ️ About", use_container_width=True):
            st.info("CaseTracker Pro - Medical Report Generation System")

    # Features section
    st.markdown("""
    <div style="margin-top: 3rem;">
        <h3 style="color: #3b82f6; margin-bottom: 1.5rem;">Features</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;">
            <div style="background: rgba(59, 130, 246, 0.1); padding: 1.5rem; border-radius: 8px; border: 1px solid rgba(59, 130, 246, 0.2);">
                <h4 style="color: #3b82f6; margin-bottom: 0.5rem;">📋 Case Report Generation</h4>
                <p style="color: #6b7280; margin: 0;">Submit case IDs and generate comprehensive medical reports with AI analysis.</p>
            </div>
            <div style="background: rgba(139, 92, 246, 0.1); padding: 1.5rem; border-radius: 8px; border: 1px solid rgba(139, 92, 246, 0.2);">
                <h4 style="color: #8b5cf6; margin-bottom: 0.5rem;">📄 Deposition Documents</h4>
                <p style="color: #6b7280; margin: 0;">Browse and view all source documents with built-in image viewer and download.</p>
            </div>
            <div style="background: rgba(16, 185, 129, 0.1); padding: 1.5rem; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.2);">
                <h4 style="color: #10b981; margin-bottom: 0.5rem;">📊 Real-time Results</h4>
                <p style="color: #6b7280; margin: 0;">View detailed results, metrics, and download generated reports.</p>
            </div>
            <div style="background: rgba(245, 158, 11, 0.1); padding: 1.5rem; border-radius: 8px; border: 1px solid rgba(245, 158, 11, 0.2);">
                <h4 style="color: #f59e0b; margin-bottom: 0.5rem;">📚 History Tracking</h4>
                <p style="color: #6b7280; margin: 0;">Access your complete report generation history and track progress.</p>
            </div>
            <div style="background: rgba(236, 72, 153, 0.1); padding: 1.5rem; border-radius: 8px; border: 1px solid rgba(236, 72, 153, 0.2);">
                <h4 style="color: #ec4899; margin-bottom: 0.5rem;">🔄 Version Comparison</h4>
                <p style="color: #6b7280; margin: 0;">Compare different versions of LCP documents to track changes section-by-section.</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick start guide
    st.markdown("""
    <div style="margin-top: 3rem;">
        <h3 style="color: #3b82f6; margin-bottom: 1.5rem;">Quick Start</h3>
        <div style="background: rgba(255, 255, 255, 0.05); padding: 1.5rem; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1);">
            <ol style="color: #6b7280; line-height: 1.8;">
                <li>Click <strong>"Case Report"</strong> to start generating a new report</li>
                <li>Enter a 4-digit Case ID when prompted</li>
                <li>Wait for the AI analysis to complete (typically 2 hours)</li>
                <li>View results and download the generated report</li>
            </ol>
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
