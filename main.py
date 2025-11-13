import streamlit as st
from streamlit_extras.switch_page_button import switch_page
import os
from dotenv import load_dotenv
import requests
# Local modules
from app.ui import inject_base_styles, show_header
from app.auth import is_authenticated, show_login_page, get_current_user, logout

def main() -> None:
    # Check authentication first
    if not is_authenticated():
        show_login_page()
        return
    
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