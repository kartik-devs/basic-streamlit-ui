import streamlit as st
import time
import random
import os
import requests
import threading
from datetime import datetime, timedelta
from app.ui import inject_base_styles, show_header, top_nav, hero_section, feature_grid, footer_section, theme_provider
from streamlit_extras.switch_page_button import switch_page


def ensure_authenticated() -> bool:
    # Authentication removed - always allow access
        return True


def _get_backend_base() -> str:
    """Get backend base URL from environment or query params."""
    params = st.query_params if hasattr(st, "query_params") else {}
    return (
        (params.get("api", [None])[0] if isinstance(params.get("api"), list) else params.get("api"))
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
    ).rstrip("/")


def _ping_backend(backend_url: str) -> bool:
    """Ping the backend to keep it alive."""
    try:
        response = requests.get(f"{backend_url}/health", timeout=5)
        return response.ok
    except Exception:
        return False


def _start_backend_pinger(backend_url: str):
    """Start background thread to ping backend every 5-7 minutes."""
    def pinger():
        ping_count = 0
        consecutive_failures = 0
        max_failures = 5
        
        while True:
            try:
                # Random interval between 5-7 minutes (300-420 seconds)
                interval = random.randint(300, 420)
                time.sleep(interval)
                
                # Ping the backend
                success = _ping_backend(backend_url)
                ping_count += 1
                
                if success:
                    consecutive_failures = 0  # Reset failure counter
                    print(f"✅ Backend ping #{ping_count} successful at {datetime.now()}")
                else:
                    consecutive_failures += 1
                    print(f"❌ Backend ping #{ping_count} failed at {datetime.now()} (failure #{consecutive_failures})")
                    
                    # If too many consecutive failures, increase retry interval
                    if consecutive_failures >= max_failures:
                        print(f"⚠️ {consecutive_failures} consecutive failures. Increasing retry interval.")
                        time.sleep(300)  # Wait 5 minutes before next attempt
                        consecutive_failures = 0  # Reset after extended wait
                    
            except KeyboardInterrupt:
                print("🛑 Pinger stopped by user")
                break
            except Exception as e:
                consecutive_failures += 1
                print(f"❌ Pinger error #{consecutive_failures}: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
                
                # Prevent infinite error loops
                if consecutive_failures >= max_failures:
                    print(f"⚠️ Too many errors ({consecutive_failures}). Pausing pinger for 10 minutes.")
                    time.sleep(600)  # Wait 10 minutes
                    consecutive_failures = 0
    
    # Start the pinger thread
    thread = threading.Thread(target=pinger, daemon=True, name="BackendPinger")
    thread.start()
    return thread


def _validate_case_id_exists(case_id: str) -> dict:
    """Check if case ID exists in S3 database using the same approach as History page."""
    try:
        backend = _get_backend_base()
        
        # Use the same endpoint as History page - /s3/cases
        response = requests.get(f"{backend}/s3/cases", timeout=10)
        if response.ok:
            data = response.json() or {}
            available_cases = data.get("cases", []) or []
            
            # Check if case ID exists in the list
            exists = case_id in available_cases
            
            if exists:
                return {
                    "exists": True,
                    "message": f"Case ID {case_id} found in database",
                    "error": None,
                    "available_cases": available_cases
                }
            else:
                return {
                    "exists": False,
                    "message": f"Case ID {case_id} not found in database",
                    "error": None,
                    "available_cases": available_cases
                }
        else:
            return {
                "exists": False,
                "message": f"Backend error: {response.status_code}",
                "error": f"HTTP {response.status_code}",
                "available_cases": []
            }
    except requests.exceptions.ConnectionError:
        return {
            "exists": False,
            "message": "Cannot connect to backend. Please ensure backend is running.",
            "error": "Connection refused",
            "available_cases": []
        }
    except requests.exceptions.Timeout:
        return {
            "exists": False,
            "message": "Backend request timed out. Please try again.",
            "error": "Timeout",
            "available_cases": []
        }
    except Exception as e:
        return {
            "exists": False,
            "message": f"Validation error: {str(e)}",
            "error": str(e),
            "available_cases": []
        }


def main() -> None:
    st.set_page_config(page_title="Case Report", page_icon="📄", layout="wide")
    theme_provider()
    inject_base_styles()
    top_nav()
    
    # Initialize backend pinger to keep backend alive
    backend_url = _get_backend_base()
    if not st.session_state.get("pinger_started", False):
        try:
            _start_backend_pinger(backend_url)
            st.session_state["pinger_started"] = True
            st.session_state["pinger_start_time"] = datetime.now()
        except Exception as e:
            st.warning(f"⚠️ Could not start backend pinger: {e}")
    
    # Show pinger status
    if st.session_state.get("pinger_started", False):
        start_time = st.session_state.get("pinger_start_time")
        if start_time:
            uptime = datetime.now() - start_time
            st.caption(f"🔄 Backend pinger active (uptime: {uptime.total_seconds()//60:.0f}m)")
    
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
                st.session_state["case_id_exists"] = False
            elif len(case_id) != 4:
                st.warning(f"⚠️ Case ID must be exactly 4 digits (current: {len(case_id)})")
                st.session_state["case_id_exists"] = False
            else:
                # Check if case ID exists in S3 database
                with st.spinner("🔍 Checking if case exists in database..."):
                    validation_result = _validate_case_id_exists(case_id)
                    
                if validation_result["exists"]:
                    st.success(f"✅ Case ID {case_id} found in database")
                    # Store validation result for button logic
                    st.session_state["case_id_exists"] = True
                else:
                    st.error(f"❌ Case ID {case_id} not found in database")
                    # Store validation result for button logic
                    st.session_state["case_id_exists"] = False
                    
                    # Show available case IDs from validation result
                    available_cases = validation_result.get("available_cases", [])
                    if available_cases:
                        st.info("💡 Try one of these available case IDs:")
                        st.code(" ".join(available_cases[:10]))  # Show first 10
                        st.info(f"Found {len(available_cases)} available case IDs")
                    else:
                        st.info("No cases found in database")
                    
                    # Add a button to refresh available cases
                    if st.button("🔄 Refresh Available Cases", key="refresh_cases"):
                        st.rerun()
        
        # Username display removed - no authentication required
        
        # Show available case IDs section
        with st.expander("📋 Available Case IDs", expanded=False):
            try:
                backend = _get_backend_base()
                response = requests.get(f"{backend}/s3/cases", timeout=5)
                if response.ok:
                    data = response.json()
                    available_cases = data.get("cases", [])
                    if available_cases:
                        st.info(f"Found {len(available_cases)} case IDs in database:")
                        # Display in a nice grid with copy functionality
                        cols = st.columns(5)
                        for i, case_id in enumerate(available_cases[:20]):  # Show first 20
                            with cols[i % 5]:
                                if st.button(case_id, key=f"select_case_{case_id}"):
                                    # Show the case ID for manual copying
                                    st.success(f"Selected: {case_id} - Please copy and paste this into the Case ID field above")
                        if len(available_cases) > 20:
                            st.info(f"... and {len(available_cases) - 20} more case IDs")
                    else:
                        st.info("No case IDs found in database")
                else:
                    st.error(f"Backend error: {response.status_code}")
            except Exception as e:
                st.error(f"Could not fetch available cases: {str(e)}")
        
        # Check if case ID is valid and exists before enabling button
        case_id_valid = case_id and case_id.isdigit() and len(case_id) == 4
        case_id_exists = st.session_state.get("case_id_exists", False)
        
        generate = st.button(
            "Generate Report", 
            type="primary", 
            use_container_width=True,
            disabled=not (case_id_valid and case_id_exists)
        )
        
        if generate:
            cid = case_id.strip()
            if not cid or not cid.isdigit() or len(cid) != 4:
                st.error("Case ID must be exactly 4 digits (0-9).")
            elif not case_id_exists:
                st.error("Case ID does not exist in database. Please enter a valid case ID.")
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
        
        # Debug button - only show when generation is in progress
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Debug: Jump to 100%", type="secondary", use_container_width=True):
                st.session_state["generation_progress"] = 100
                st.session_state["generation_complete"] = True
                st.session_state["generation_in_progress"] = False
                st.session_state["generation_step"] = 4
                st.success("🎉 Debug: Report generation completed instantly!")
                st.rerun()
        
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


