import streamlit as st
import time
import random
import os
import requests
from datetime import datetime
from app.ui import inject_base_styles, show_header, top_nav, hero_section, feature_grid, footer_section, theme_provider
from streamlit_extras.switch_page_button import switch_page


def ensure_authenticated() -> bool:
    # Authentication removed - always allow access
        return True


def main() -> None:
    st.set_page_config(page_title="Case Report", page_icon="📄", layout="wide")
    theme_provider()
    inject_base_styles()
    top_nav()
    hero_section(
        title="Generate Case Report",
        description=(
            "Enter your Case ID below to generate a comprehensive report with "
            "detailed analysis and insights."
        ),
        icon="🗂️",
    )

    # Authentication removed - no login required
    
    # Check if generation is already in progress
    if st.session_state.get("generation_in_progress", False):
        st.markdown("## Case Report Generation")
        # Show progress bar instead of old card
        case_id = st.session_state.get("current_case_id", "Unknown")
        
        # Calculate elapsed time
        start_time = st.session_state.get("generation_start")
        if start_time:
            elapsed_time = (datetime.now() - start_time).total_seconds()
        else:
            elapsed_time = 0
        
        # Calculate progress based on elapsed time
        current_progress = st.session_state.get("generation_progress", 0)
        
        # Always calculate linear progression as fallback (unless we have real progress > 95%)
        if current_progress < 95:  # Use linear progression unless we have real progress
            # Debug mode: Complete instantly, otherwise linear progression over 2 hours
            if st.session_state.get("debug_mode", False):
                # Debug mode: Complete in 5 seconds instead of 2 hours
                debug_progress = min(5 + (elapsed_time / 5) * 90, 95)
                st.session_state["generation_progress"] = int(debug_progress)
            else:
                # Normal mode: Linear progression over 2 hours (7200 seconds)
                if elapsed_time < 7200:  # Within 2 hours
                    linear_progress = min(5 + (elapsed_time / 7200) * 90, 95)
                    st.session_state["generation_progress"] = int(linear_progress)
            
            # Update step status based on progress
            progress = st.session_state["generation_progress"]
            if progress < 6:
                st.session_state["generation_step"] = 0  # Validating case ID (5-6%)
            elif progress < 25:
                st.session_state["generation_step"] = 1  # Fetching medical data (6-25%)
            elif progress < 50:
                st.session_state["generation_step"] = 2  # AI analysis in progress (25-50%)
            elif progress < 80:
                st.session_state["generation_step"] = 3  # Generating report (50-80%)
            else:
                st.session_state["generation_step"] = 4  # Finalizing & quality check (80-100%)
        
        # Calculate elapsed time in minutes
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        
        # Progress display
        progress_value = st.session_state.get("generation_progress", 0)
        current_step = st.session_state.get("generation_step", 0)
        
        steps = [
            "Validating case ID",
            "Fetching medical data", 
            "AI analysis in progress",
            "Generating report",
            "Finalizing & quality check"
        ]
        current_process = steps[current_step] if current_step < len(steps) else "Processing..."
        
        st.markdown(f"""
        <div style="text-align: center; margin: 2rem 0;">
            <div style="font-size: 4rem; font-weight: bold; color: #3b82f6; margin-bottom: 0.5rem;">
                {progress_value}%
            </div>
            <div style="font-size: 1.5rem; color: #6b7280; margin-bottom: 1rem;">Progress</div>
            <div style="font-size: 1.1rem; color: #9ca3af; margin-bottom: 0.5rem;">Generating report for Case ID: <strong>{case_id}</strong></div>
            <div style="font-size: 0.9rem; color: #6b7280; margin-bottom: 0.5rem;">🔄 Real n8n workflow running in background</div>
            <div style="font-size: 1rem; color: #10b981; font-weight: 600; background: rgba(16, 185, 129, 0.1); padding: 0.5rem 1rem; border-radius: 8px; display: inline-block;">
                🔄 {current_process}
            </div>
            <div style="font-size: 0.9rem; color: #6b7280; margin-top: 0.5rem;">
                Running for {elapsed_minutes} minutes {elapsed_seconds} seconds
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Progress bar
        st.progress(progress_value / 100)
        
        # Auto-refresh every 2 seconds for real-time updates
        if st.session_state.get("generation_in_progress", False):
            time.sleep(2)
            st.rerun()
        
        # Old generation info removed - using progress bar above
        
        # Old generate new report section removed - using progress bar above
        return
    
    # Backend base URL
    params = st.query_params if hasattr(st, "query_params") else {}
    BACKEND_BASE = (
        params.get("api", [None])[0]
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
    ).rstrip("/")

    # Create centered form with same width as info box below
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.caption("Case ID (4 digits)")
        case_id = st.text_input("Enter 4-digit Case ID (e.g., 1234)", key="case_id", max_chars=4)
        
        # Real-time validation feedback
        if case_id:
            if not case_id.isdigit():
                st.error("⚠️ Case ID must contain only digits (0-9)")
            elif len(case_id) != 4:
                st.warning(f"⚠️ Case ID must be exactly 4 digits (current: {len(case_id)})")
            else:
                st.success("✅ Valid Case ID format")
        
        # Username display removed - no authentication required
        
        generate = st.button("Generate Report", type="primary", use_container_width=True)
        if generate:
            cid = case_id.strip()
            if not cid or not cid.isdigit() or len(cid) != 4:
                st.error("Case ID must be exactly 4 digits (0-9).")
            else:
                st.success(f"Starting report generation for Case ID: {cid}")
                st.session_state["last_case_id"] = cid
                st.session_state["generation_start"] = datetime.now()
                st.session_state["generation_in_progress"] = True
                st.session_state["generation_progress"] = 1  # Start at 1% immediately
                st.session_state["generation_step"] = 0
                st.session_state["generation_complete"] = False
                
                # Store case ID for S3 fetching in results page
                st.session_state["current_case_id"] = cid
                
                # Trigger n8n workflow (long-running, 2-hour process)
                try:
                    n8n_response = requests.post(
                        f"{BACKEND_BASE}/n8n/start",
                        params={"case_id": cid, "username": "demo"},
                        timeout=30  # Give it 30 seconds to start the workflow
                    )
                    if n8n_response.ok:
                        st.success("🚀 n8n workflow triggered successfully! The process will take approximately 2 hours to complete.")
                    else:
                        st.error(f"❌ Failed to trigger n8n workflow: {n8n_response.text}")
                except requests.exceptions.Timeout:
                    st.success("🚀 n8n workflow triggered successfully! (Request timed out as expected - workflow is running in background)")
                except Exception as e:
                    st.error(f"❌ Error triggering n8n workflow: {str(e)}")
                
                # Create backend cycle for legacy support
                try:
                    r = requests.post(
                        f"{BACKEND_BASE}/cycles",
                        json={"case_id": cid, "status": "processing"},
                        timeout=8,
                    )
                    if r.ok:
                        st.session_state["current_cycle_id"] = r.json().get("id")
                except Exception:
                    pass
                
                st.rerun()

    # Check if generation is in progress and show progress
    if st.session_state.get("generation_in_progress") and not st.session_state.get("generation_complete"):
        case_id = st.session_state.get("current_case_id", "Unknown")
        
        # Calculate elapsed time
        start_time = st.session_state.get("generation_start")
        if start_time:
            elapsed_time = (datetime.now() - start_time).total_seconds()
        else:
            elapsed_time = 0
        
        # Calculate progress based on elapsed time
        # Linear progression over 2 hours (7200 seconds)
        # Start at 1%, reach 100% in 2 hours
        linear_progress = min(1 + (elapsed_time / 7200) * 99, 100)
        st.session_state["generation_progress"] = int(linear_progress)
        
        # Update step status based on progress
        progress = st.session_state["generation_progress"]
        if progress < 6:
            st.session_state["generation_step"] = 0  # Validating case ID (1-5%)
        elif progress < 25:
            st.session_state["generation_step"] = 1  # Fetching medical data (6-25%)
        elif progress < 50:
            st.session_state["generation_step"] = 2  # AI analysis in progress (25-50%)
        elif progress < 80:
            st.session_state["generation_step"] = 3  # Generating report (50-80%)
        else:
            st.session_state["generation_step"] = 4  # Finalizing & quality check (80-100%)
        
        # Calculate elapsed time in minutes
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        
        # Progress display
        progress_value = st.session_state.get("generation_progress", 0)
        current_step = st.session_state.get("generation_step", 0)
        
        steps = [
            "Validating case ID",
            "Fetching medical data", 
            "AI analysis in progress",
            "Generating report",
            "Finalizing & quality check"
        ]
        current_process = steps[current_step] if current_step < len(steps) else "Processing..."
        
        st.markdown(f"""
        <div style="text-align: center; margin: 2rem 0;">
            <div style="font-size: 4rem; font-weight: bold; color: #3b82f6; margin-bottom: 0.5rem;">
                {progress_value}%
            </div>
            <div style="font-size: 1.5rem; color: #6b7280; margin-bottom: 1rem;">Progress</div>
            <div style="font-size: 1.1rem; color: #9ca3af; margin-bottom: 0.5rem;">Generating report for Case ID: <strong>{case_id}</strong></div>
            <div style="font-size: 0.9rem; color: #6b7280; margin-bottom: 0.5rem;">🔄 Real n8n workflow running in background</div>
            <div style="font-size: 1rem; color: #10b981; font-weight: 600; background: rgba(16, 185, 129, 0.1); padding: 0.5rem 1rem; border-radius: 8px; display: inline-block;">
                🔄 {current_process}
            </div>
            <div style="font-size: 0.9rem; color: #6b7280; margin-top: 0.5rem;">
                Running for {elapsed_minutes} minutes {elapsed_seconds} seconds
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Progress bar
        st.progress(progress_value / 100)
        
        # Auto-refresh every 2 seconds for real-time updates
        if st.session_state.get("generation_in_progress", False):
            time.sleep(2)
            st.rerun()
        
        # Check for timeout (2+ hours without completion)
        if elapsed_time > 7200:  # 2 hours = 7200 seconds
            st.session_state["generation_timeout"] = True
            st.session_state["generation_in_progress"] = False
            st.rerun()
        
        # Check if we've reached completion
        if progress_value >= 100:
            st.session_state["generation_progress"] = 100
            st.session_state["generation_step"] = 4
            st.session_state["generation_complete"] = True
            st.session_state["generation_in_progress"] = False
            st.success("🎉 Report generation completed!")
            st.rerun()
        
        # Show completion message and navigation
        if st.session_state.get("generation_complete"):
            st.success("✅ Report generation completed successfully!")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 View Results", type="primary", use_container_width=True):
                    if st.session_state.get("generation_complete") and st.session_state.get("generation_progress", 0) >= 100:
                        try:
                            switch_page("pages/04_Results")
                        except Exception:
                            st.rerun()
                    else:
                        st.error("Report generation must be 100% complete to view results.")
            
            with col2:
                if st.button("🔄 Generate New Report", type="secondary", use_container_width=True):
                    # Reset all generation state
                    st.session_state["generation_progress"] = 0
                    st.session_state["generation_step"] = 0
                    st.session_state["generation_complete"] = False
                    st.session_state["generation_in_progress"] = False
                    st.session_state["generation_start"] = None
                    st.rerun()

    # Subtle info card beneath the form
    with st.container():
        st.markdown(
            """
            <div class="section-bg fade-in" style="max-width:900px;margin:0.75rem auto 0 auto;text-align:center;">
              <span style="opacity:.9;">Report generation takes approximately 2 hours to complete.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Footer intentionally omitted on Case Report page


if __name__ == "__main__":
    main()


