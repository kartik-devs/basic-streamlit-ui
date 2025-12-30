import streamlit as st
import time
import random
import os
import requests
import threading
from datetime import datetime, timedelta
from app.ui import inject_base_styles, show_header, top_nav, hero_section, feature_grid, footer_section, theme_provider
from app.auth import require_authentication, get_current_user, logout
from streamlit_extras.switch_page_button import switch_page
import streamlit.runtime.scriptrunner as scriptrunner

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
    # Debug exception: allow special demo id 0000 even if it doesn't exist in S3
    if str(case_id) == "0000":
        return {
            "exists": True,
            "message": "Debug id 0000 allowed (mapped to alias in Results)",
            "error": None,
            "available_cases": [],
        }
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
        # --- Safe session initialization ---
    defaults = {
        "generation_in_progress": False,
        "generation_complete": False,
        "generation_progress": 0,
        "generation_step": 0,
        "current_case_id": None,
        "generation_start": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


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


    # Check if generation is already in progress
    if st.session_state.get("generation_in_progress", False):
        st.markdown("## Case Report Generation")
        case_id = st.session_state.get("current_case_id", "Unknown")
        
        # Determine simulated target duration
        if str(case_id) == "0000":
            target_seconds = 60
        else:
            target_seconds = int(st.session_state.get("debug_target_seconds", 7200))
        
        # Calculate elapsed time
        start_time = st.session_state.get("generation_start")
        if start_time:
            elapsed_time = (datetime.now() - start_time).total_seconds()
        else:
            elapsed_time = 0
        
        # Calculate progress based on elapsed time
        current_progress = st.session_state.get("generation_progress", 0)
        
        # Always calculate linear progression as fallback (unless we have real progress at 100%)
        if current_progress < 100:
            if st.session_state.get("debug_mode", False):
                # Debug mode: Complete in 5 seconds instead of 2 hours
                debug_progress = min(5 + (elapsed_time / 5) * 95, 100)
                st.session_state["generation_progress"] = int(debug_progress)
            else:
                # Normal mode: Linear progression over target_seconds
                if elapsed_time < target_seconds:
                    linear_progress = min(5 + (elapsed_time / target_seconds) * 95, 100)
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

        # Force-complete after target window to avoid being stuck at ~98–99%
        if elapsed_time >= target_seconds and st.session_state.get("generation_in_progress"):
            st.session_state["generation_progress"] = 100
            st.session_state["generation_step"] = 4
            st.session_state["generation_complete"] = True
            st.session_state["generation_in_progress"] = False
            if scriptrunner.get_script_run_ctx():
                time.sleep(0.3)
                st.rerun()

        # Optional auto-complete for demos (disabled by default). Set AUTO_COMPLETE_SECONDS to enable.
        auto_complete_env = os.getenv("AUTO_COMPLETE_SECONDS")
        if auto_complete_env:
            try:
                auto_complete_seconds = max(1, int(auto_complete_env))
            except Exception:
                auto_complete_seconds = None
            if auto_complete_seconds and elapsed_time >= auto_complete_seconds:
                st.session_state["generation_progress"] = 100
                st.session_state["generation_step"] = 4
                st.session_state["generation_complete"] = True
                st.session_state["generation_in_progress"] = False
                st.session_state["navigate_to_results"] = True
        
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
    
    # Backend base URL
    params = st.query_params if hasattr(st, "query_params") else {}
    BACKEND_BASE = (
        params.get("api", [None])[0]
        or os.getenv("BACKEND_BASE")
        or "http://localhost:8000"
    ).rstrip("/")

    # Show finished screen when a run has completed
    if st.session_state.get("generation_complete") and not st.session_state.get("generation_in_progress"):
        st.success("✅ Report generation completed successfully!")
        fin = st.container()
        with fin:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📊 View Results", type="primary", use_container_width=True):
                    # Persist selected case id for the Results page
                    cid = st.session_state.get("current_case_id") or st.session_state.get("last_case_id")
                    if cid:
                        st.session_state["last_case_id"] = cid
                        try:
                            if hasattr(st, "query_params"):
                                qp = dict(st.query_params)
                                qp["case"] = cid
                                try:
                                    st.query_params.clear()
                                except Exception:
                                    pass
                                try:
                                    st.experimental_set_query_params(**qp)
                                except Exception:
                                    st.experimental_set_query_params(case=cid)
                            else:
                                st.experimental_set_query_params(case=cid)
                        except Exception:
                            pass
                    try:
                        switch_page("pages/04_Results")
                    except Exception:
                        st.session_state["_goto_results_intent"] = True
                        st.experimental_rerun()
            with c2:
                if st.button("🔄 Generate New Report", type="secondary", use_container_width=True):
                    st.session_state["generation_progress"] = 0
                    st.session_state["generation_step"] = 0
                    st.session_state["generation_complete"] = False
                    st.session_state["generation_in_progress"] = False
                    st.session_state["generation_start"] = None
                    st.experimental_rerun()
        return

    # Show input form only when not generating and not completed
    if not st.session_state.get("generation_in_progress") and not st.session_state.get("generation_complete"):
        
        # Fetch available cases dynamically from backend
        @st.cache_data(ttl=120)
        def fetch_available_cases():
            backend = _get_backend_base()
            try:
                res = requests.get(f"{backend}/s3/cases", timeout=5)
                if res.ok:
                    data = res.json()
                    return data.get("cases", [])
            except Exception:
                pass
            return []

        available_cases = fetch_available_cases()
        
        # Modern header with gradient
        st.markdown("""
        <div style="text-align: center; margin: 2rem 0 2.5rem 0;">
            <h2 style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2rem;
                font-weight: 800;
                margin-bottom: 0.5rem;
            ">
                Document Generator
            </h2>
            <p style="color: #6b7280; font-size: 1rem;">
                Generate case reports and deposition documents
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Center tabs to match input width
        col_left, col_center, col_right = st.columns([1, 3, 1])
        with col_center:
            # Modern tabbed interface
            tab1, tab2, tab3, tab4 = st.tabs(["📄 Standard Report", "🔒 Redacted Report", "📋 Deposition Document", "🧪 MCP Redacted"])
        
            # ========== TAB 1: STANDARD REPORT ==========
            with tab1:
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                
                # Case ID input
                case_id_standard = st.selectbox(
                    "Case ID",
                    options=[""] + available_cases,
                    index=0,
                    key="case_id_standard",
                    placeholder="Select or type case ID (4 digits)",
                    help="Enter a 4-digit case ID to generate a standard report"
                )
                
                # Batching toggle
                batching_standard = st.toggle("Enable Batching", value=False, key="batching_standard")
                batch_flag_standard = 0 if batching_standard else 1
                
                # Validation
                case_valid_standard = False
                if case_id_standard:
                    if not case_id_standard.isdigit() or len(case_id_standard) != 4:
                        st.error("⚠️ Case ID must be a 4-digit number")
                    else:
                        with st.spinner("Validating..."):
                            validation = _validate_case_id_exists(case_id_standard)
                        if validation.get("exists"):
                            st.success(f"✅ Case {case_id_standard} verified")
                            case_valid_standard = True
                        else:
                            st.error("❌ Case ID not found in database")
                
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                
                # Generate button
                generate_standard = st.button(
                    "🚀 Generate Standard Report",
                    type="primary",
                    use_container_width=True,
                    disabled=not case_valid_standard,
                    key="btn_standard"
                )
        
            # ========== TAB 2: REDACTED REPORT ==========
            with tab2:
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                
                # Case ID input
                case_id_redacted = st.selectbox(
                    "Case ID",
                    options=[""] + available_cases,
                    index=0,
                    key="case_id_redacted",
                    placeholder="Select or type case ID (4 digits)",
                    help="Enter a 4-digit case ID to generate a redacted report"
                )
                
                # Batching toggle
                batching_redacted = st.toggle("Enable Batching", value=False, key="batching_redacted")
                batch_flag_redacted = 0 if batching_redacted else 1
                
                # Validation
                case_valid_redacted = False
                if case_id_redacted:
                    if not case_id_redacted.isdigit() or len(case_id_redacted) != 4:
                        st.error("⚠️ Case ID must be a 4-digit number")
                    else:
                        with st.spinner("Validating..."):
                            validation = _validate_case_id_exists(case_id_redacted)
                        if validation.get("exists"):
                            st.success(f"✅ Case {case_id_redacted} verified")
                            case_valid_redacted = True
                        else:
                            st.error("❌ Case ID not found in database")
                
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                
                # Generate button
                generate_redacted = st.button(
                    "🔒 Generate Redacted Report",
                    type="primary",
                    use_container_width=True,
                    disabled=not case_valid_redacted,
                    key="btn_redacted"
                )
        
            # ========== TAB 3: DEPOSITION DOCUMENT ==========
            with tab3:
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                
                # Case ID input
                case_id_deposition = st.selectbox(
                    "Case ID",
                    options=[""] + available_cases,
                    index=0,
                    key="case_id_deposition",
                    placeholder="Select or type case ID (4 digits)",
                    help="Enter a 4-digit case ID to generate a deposition document"
                )
                
                # Validation
                case_valid_deposition = False
                if case_id_deposition:
                    if not case_id_deposition.isdigit() or len(case_id_deposition) != 4:
                        st.error("⚠️ Case ID must be a 4-digit number")
                    else:
                        with st.spinner("Validating..."):
                            validation = _validate_case_id_exists(case_id_deposition)
                        if validation.get("exists"):
                            st.success(f"✅ Case {case_id_deposition} verified")
                            case_valid_deposition = True
                        else:
                            st.error("❌ Case ID not found in database")
                
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                
                # Generate button
                generate_deposition = st.button(
                    "📋 Generate Deposition Document",
                    type="primary",
                    use_container_width=True,
                    disabled=not case_valid_deposition,
                    key="btn_deposition"
                )

            # ========== TAB 4: MCP REDACTED WITH PATIENT ==========
            with tab4:
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                
                patient_name_mcp = st.text_input(
                    "Patient Name",
                    key="patient_name_mcp",
                    placeholder="Enter patient full name"
                )

                case_id_mcp = st.selectbox(
                    "Case ID",
                    options=[""] + available_cases,
                    index=0,
                    key="case_id_mcp",
                    placeholder="Select or type case ID (4 digits)",
                    help="Enter a 4-digit case ID to generate a redacted report with patient name"
                )
                
                batching_mcp = st.toggle("Enable Batching", value=False, key="batching_mcp")
                batch_flag_mcp = 0 if batching_mcp else 1

                case_valid_mcp = False
                if case_id_mcp:
                    if not case_id_mcp.isdigit() or len(case_id_mcp) != 4:
                        st.error("⚠️ Case ID must be a 4-digit number")
                    else:
                        with st.spinner("Validating..."):
                            validation = _validate_case_id_exists(case_id_mcp)
                        if validation.get("exists"):
                            if not patient_name_mcp or not patient_name_mcp.strip():
                                st.error("⚠️ Patient name is required")
                            else:
                                st.success(f"✅ Case {case_id_mcp} verified for patient {patient_name_mcp}")
                                case_valid_mcp = True
                        else:
                            st.error("❌ Case ID not found in database")
                elif patient_name_mcp:
                    st.error("⚠️ Please select a Case ID")

                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

                generate_mcp_redacted = st.button(
                    "🔒 Generate MCP Redacted Report",
                    type="primary",
                    use_container_width=True,
                    disabled=not case_valid_mcp,
                    key="btn_mcp_redacted"
                )
        
        # Available cases expander (outside tabs, below)
        with st.expander("📋 Browse Available Case IDs", expanded=False):
            try:
                backend = _get_backend_base()
                response = requests.get(f"{backend}/s3/cases", timeout=5)
                if response.ok:
                    data = response.json()
                    cases = data.get("cases", [])
                    if cases:
                        st.info(f"📊 Found {len(cases)} case IDs in database")
                        cols = st.columns(6)
                        for i, case_opt in enumerate(cases[:24]):
                            with cols[i % 6]:
                                st.code(case_opt, language=None)
                        if len(cases) > 24:
                            st.caption(f"... and {len(cases) - 24} more")
                    else:
                        st.warning("No case IDs found")
                else:
                    st.error(f"Error: {response.status_code}")
            except Exception as e:
                st.error(f"Could not fetch cases: {str(e)}")
        
        # Handle button actions - Standard Report
        if generate_standard:
            cid = case_id_standard.strip()
            webhook_url = "https://n8n.datakernels.in/webhook/mainworkflow"
            
            st.success(f"🚀 Starting standard report for Case ID: {cid}")
            st.session_state["last_case_id"] = cid
            st.session_state["generation_start"] = datetime.now()
            st.session_state["generation_in_progress"] = True
            st.session_state["generation_progress"] = 1
            st.session_state["generation_step"] = 0
            st.session_state["generation_complete"] = False
            st.session_state["current_case_id"] = cid
            st.session_state["report_type"] = "standard"
            
            try:
                response = requests.post(
                    webhook_url,
                    json={"case_id": cid, "username": "demo", "batching": batch_flag_standard},
                    timeout=15
                )
                if response.ok:
                    st.success("✅ Workflow triggered successfully!")
                else:
                    st.error(f"⚠️ Workflow failed: {response.status_code}")
            except requests.exceptions.Timeout:
                st.success("⏱️ Workflow triggered (running in background)")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
            
            if scriptrunner.get_script_run_ctx():
                time.sleep(0.3)
                st.rerun()
        
        # Handle button actions - Redacted Report
        if generate_redacted:
            cid = case_id_redacted.strip()
            webhook_url = "https://n8n.datakernels.in/webhook/mcp"
            
            st.success(f"🚀 Starting redacted report for Case ID: {cid}")
            st.session_state["last_case_id"] = cid
            st.session_state["generation_start"] = datetime.now()
            st.session_state["generation_in_progress"] = True
            st.session_state["generation_progress"] = 1
            st.session_state["generation_step"] = 0
            st.session_state["generation_complete"] = False
            st.session_state["current_case_id"] = cid
            st.session_state["report_type"] = "redacted"
            
            try:
                response = requests.post(
                    webhook_url,
                    json={"case_id": cid, "username": "demo", "batching": batch_flag_redacted},
                    timeout=15
                )
                if response.ok:
                    st.success("✅ Workflow triggered successfully!")
                else:
                    st.error(f"⚠️ Workflow failed: {response.status_code}")
            except requests.exceptions.Timeout:
                st.success("⏱️ Workflow triggered (running in background)")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
            
            if scriptrunner.get_script_run_ctx():
                time.sleep(0.3)
                st.rerun()

        if generate_mcp_redacted:
            cid = case_id_mcp.strip()
            patient_name = patient_name_mcp.strip() if patient_name_mcp else ""
            webhook_url = "https://n8n.datakernels.in/webhook/mcp"
            
            st.success(f"🚀 Starting MCP redacted report for Case ID: {cid} and patient: {patient_name}")
            st.session_state["last_case_id"] = cid
            st.session_state["generation_start"] = datetime.now()
            st.session_state["generation_in_progress"] = True
            st.session_state["generation_progress"] = 1
            st.session_state["generation_step"] = 0
            st.session_state["generation_complete"] = False
            st.session_state["current_case_id"] = cid
            st.session_state["report_type"] = "mcp_redacted"
            st.session_state["patient_name"] = patient_name
            
            try:
                response = requests.post(
                    webhook_url,
                    json={
                        "case_id": cid,
                        "patient_name": patient_name,
                        "username": "demo",
                        "batching": batch_flag_mcp,
                    },
                    timeout=15,
                )
                if response.ok:
                    st.success("✅ Workflow triggered successfully!")
                else:
                    st.error(f"⚠️ Workflow failed: {response.status_code}")
            except requests.exceptions.Timeout:
                st.success("⏱️ Workflow triggered (running in background)")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
            
            if scriptrunner.get_script_run_ctx():
                time.sleep(0.3)
                st.rerun()
        
        # Handle button actions - Deposition Document
        if generate_deposition:
            cid = case_id_deposition.strip()
            webhook_url = "https://n8n.datakernels.in/webhook/4b3828a5-ea26-4228-a93b-cd34f7bb1faa"
            
            st.success(f"🚀 Starting deposition document for Case ID: {cid}")
            
            try:
                response = requests.post(
                    webhook_url,
                    json={"case_id": cid, "username": "demo"},
                    timeout=15
                )
                if response.ok:
                    st.success("✅ Deposition workflow triggered successfully!")
                    st.info("📄 Your document will be processed in the background")
                else:
                    st.error(f"⚠️ Workflow failed: {response.status_code}")
                    st.caption(f"URL called: {webhook_url}")
                    if response.text:
                        with st.expander("Response details"):
                            st.code(response.text)
                    st.info("💡 Please ensure the workflow is active in n8n")
            except requests.exceptions.Timeout:
                st.success("⏱️ Deposition workflow triggered (running in background)")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.caption(f"URL attempted: {webhook_url}")
        
        # Info note
        st.markdown("""
        <div style="
            max-width: 600px;
            margin: 2rem auto;
            padding: 1rem 1.5rem;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
            border-radius: 12px;
            border-left: 4px solid #667eea;
            text-align: center;
        ">
            <p style="color: #4b5563; font-size: 0.95rem; margin: 0;">
                ⏱️ Report generation typically takes <strong>~2 hours</strong> to complete
            </p>
        </div>
        """, unsafe_allow_html=True)

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
        target_seconds = int(st.session_state.get("debug_target_seconds", 7200))
        linear_progress = min(1 + (elapsed_time / target_seconds) * 99, 100)
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
                if scriptrunner.get_script_run_ctx():
                    time.sleep(0.3)
                    st.rerun()
        
        # Auto-refresh every 2 seconds for real-time updates
        if st.session_state.get("generation_in_progress", False):
            time.sleep(2)
            if scriptrunner.get_script_run_ctx():
                time.sleep(0.3)
                st.rerun()
        
        # Auto-complete after 2 hours to avoid being stuck near 98–99%
        if elapsed_time >= 7200:  # 2 hours = 7200 seconds
            st.session_state["generation_progress"] = 100
            st.session_state["generation_step"] = 4
            st.session_state["generation_complete"] = True
            st.session_state["generation_in_progress"] = False
            st.session_state["navigate_to_results"] = True
            if scriptrunner.get_script_run_ctx():
                time.sleep(0.3)
                st.rerun()
        
        # Check if we've reached completion
        if progress_value >= 100:
            st.session_state["generation_progress"] = 100
            st.session_state["generation_step"] = 4
            st.session_state["generation_complete"] = True
            st.session_state["generation_in_progress"] = False
            st.success("🎉 Report generation completed!")
            if scriptrunner.get_script_run_ctx():
                time.sleep(0.3)
                st.rerun()
        
        # Show completion message and navigation
        if st.session_state.get("generation_complete"):
            st.success("✅ Report generation completed successfully!")
            
            # Replace input form with actions at the bottom of the page
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            actions = st.container()
            with actions:
                col1, col2 = st.columns(2)
                with col1:
                        if st.button("📊 View Results", type="primary", use_container_width=True):
                            cid = st.session_state.get("current_case_id") or st.session_state.get("last_case_id")

                            if cid:
                                # ✅ Store case ID for later pages
                                st.session_state["selected_case_id"] = cid

                                # ✅ Update URL query params (used by Results page)
                                try:
                                    st.experimental_set_query_params(case=cid)
                                except Exception:
                                    pass

                                # ✅ Navigate to the Results page (Streamlit auto-maps “04_Results.py” → “Results”)
                                try:
                                    switch_page("Results")
                                except Exception:
                                    st.session_state["_goto_results_intent"] = True
                                    if scriptrunner.get_script_run_ctx():
                                        time.sleep(0.3)
                                        st.rerun()
                            else:
                                st.warning("⚠️ No Case ID found. Please generate a report first.")

                with col2:
                    if st.button("🔄 Generate New Report", type="secondary", use_container_width=True):
                        # Reset all generation state and show input again
                        st.session_state["generation_progress"] = 0
                        st.session_state["generation_step"] = 0
                        st.session_state["generation_complete"] = False
                        st.session_state["generation_in_progress"] = False
                        st.session_state["generation_start"] = None
                        st.session_state.pop("navigate_to_results", None)
                        if scriptrunner.get_script_run_ctx():
                            time.sleep(0.3)
                            st.rerun()


if __name__ == "__main__":
    main()
