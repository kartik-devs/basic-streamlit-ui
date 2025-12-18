import streamlit as st
from streamlit_extras.switch_page_button import switch_page
import os
from dotenv import load_dotenv
import requests
import time

# Local modules
from app.ui import inject_base_styles, show_header
from app.auth import is_authenticated, show_login_page, get_current_user, logout

# =========================================================
# 🔒 SECURE DOCUMENT GATEKEEPER (TOP LEVEL EXECUTION)
# =========================================================
# This runs immediately. If a document ID is found in the URL,
# it hijack the app to show the secure viewer and stops.
query_params = st.query_params
doc_id = query_params.get("doc_id", None)

if doc_id:
    # 1. Configure page for Secure Viewing (Centered, Simple)
    st.set_page_config(page_title="Secure Evidence Viewer", layout="centered")
    
    # 2. Secure UI
    st.title("🔒 Secure Evidence Gateway")
    st.info(f"Incoming Request for Evidence ID: **{doc_id}**")
    st.markdown("---")

    # 3. Authentication
    password = st.text_input("Enter Case Access Code to view this file:", type="password")
    
    if password == "legal2025":  
        with st.spinner("Authenticating & Retrieving Evidence..."):
            time.sleep(1) # Security delay simulation
            
            # --- REAL APP LOGIC: Fetch from S3 would go here ---
            # image_data = s3_client.get_object(...)
            
            st.success("Access Granted.")
            
            # Display the document
            st.image(
                "https://placehold.co/600x800/png?text=Confidential+Medical+Record", 
                caption=f"Source ID: {doc_id}",
                use_container_width=True
            )
            
            st.warning("⚠️ CONFIDENTIAL: Access logged. Do not distribute.")
            
            if st.button("Return to Dashboard"):
                st.query_params.clear()
                st.rerun()
                
    elif password:
        st.error("⛔ Access Denied: Invalid Credentials")
        
    # 4. STOP execution so the main dashboard doesn't load in the background
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
    # This runs only if doc_id was NOT present
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
