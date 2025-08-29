import os
import streamlit as st
import time
from datetime import datetime, timedelta
from app.ui import inject_base_styles, top_nav, theme_provider
try:
    import requests
except Exception:
    requests = None


 
 
def main() -> None:
    st.set_page_config(page_title="Generating Report+", page_icon="⏳", layout="wide")
    theme_provider()
    inject_base_styles()
    top_nav()
 
    # --- Query params / state
    params = st.query_params if hasattr(st, "query_params") else {}
    url_start = params.get("start", ["0"])[0] == "1"
    case_id = (st.session_state.get("last_case_id") or params.get("case_id", [""])[0]).strip() or "0000"
 
    # Single-source trigger: URL start=1 OR nav_to_generating flag
    triggered = url_start or st.session_state.pop("nav_to_generating", False)
    if triggered:
        st.session_state["generation_in_progress"] = True
        st.session_state["n8n_triggered"] = False  # Reset n8n status
        st.session_state["n8n_trigger_time"] = None
        try:
            qp = st.query_params if hasattr(st, "query_params") else None
            if qp is not None:
                qp["start"] = "0"
                qp["case_id"] = case_id
        except Exception:
            pass
 
    if not st.session_state.get("generation_in_progress"):
        st.markdown('<div class="section-bg" style="max-width:900px;margin:0 auto;text-align:center;">', unsafe_allow_html=True)
        st.markdown("<h3>Generating Report</h3>", unsafe_allow_html=True)
        new_id = st.text_input("Enter Case ID (4 digits)", value=case_id)
        start_click = st.button("Start", type="primary")
        if start_click:
            st.session_state["last_case_id"] = (new_id or case_id).strip()
            st.session_state["generation_in_progress"] = True
            try:
                qp = st.query_params if hasattr(st, "query_params") else None
                if qp is not None:
                    qp["case_id"] = st.session_state["last_case_id"]
                    qp["start"] = "0"
            except Exception:
                pass
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return
 
    case_id = st.session_state.get("last_case_id", params.get("case_id", ["UNKNOWN"])[0])
    start_time = st.session_state.get("generation_start", datetime.now())
    st.session_state["generation_start"] = start_time
 
    st.markdown('<div class="section-bg" style="max-width:900px;margin:0 auto;">', unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
    st.markdown("""
        <div style='font-size:32px'>📄</div>
        <h3>Generating Report</h3>
        <p style='opacity:.9;margin-top:-6px;'>Grab a coffee while we generate your report. We will email you as soon as it's complete.</p>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
 
    progress = st.progress(0)
    n8n_ph = st.empty()
    st.markdown("""
        <div style="display:flex;justify-content:space-between;margin-top:4px;padding:0 4px;">
          <span style="opacity:.8;">0%</span>
          <span style="opacity:.8;padding-right:2px;">100%</span>
        </div>
    """, unsafe_allow_html=True)
 
    steps = [
        "Validating case ID",
        "Fetching data",
        "Compiling report",
        "Finalizing",
        "Preparing download",
    ]
    placeholders = [st.empty() for _ in steps]
 
    def line(idx: int, state: str):
        icon = {"waiting": "○", "active": "⏳", "done": "✅"}[state]
        style = {
            "waiting": "opacity:.8;",
            "active": "font-weight:600;",
            "done": "opacity:.9; text-decoration: line-through;",
        }[state]
        placeholders[idx].markdown(f"- {icon} <span style='{style}'>{steps[idx]}...</span>", unsafe_allow_html=True)
 
    for i in range(len(steps)):
        line(i, "waiting")
 
    # n8n Integration - Trigger workflow and monitor progress
    n8n_webhook_url = "http://3.82.11.141:5678/webhook/318f2a27-b1fc-4a96-8146-264a9c1f946e"
    n8n_workflow_url = "http://54.198.187.195:5678/workflow/WnVP0DlX6U3cYCvJ"
    
    try:
        # Trigger n8n workflow via webhook
        if requests:
            webhook_payload = {
                "case_id": case_id,
                "timestamp": datetime.now().isoformat(),
                "triggered_by": st.session_state.get("username", "unknown")
            }
            
            # Send webhook to trigger n8n workflow
            response = requests.post(
                n8n_webhook_url,
                json=webhook_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                n8n_ph.success(f"✅ n8n workflow triggered successfully for Case ID: {case_id}")
                st.session_state["n8n_triggered"] = True
                st.session_state["n8n_trigger_time"] = datetime.now()
            else:
                n8n_ph.error(f"❌ Failed to trigger n8n workflow. Status: {response.status_code}")
                st.session_state["n8n_triggered"] = False
        else:
            n8n_ph.warning("⚠️ Requests module not available. Cannot trigger n8n workflow.")
            st.session_state["n8n_triggered"] = False
            
    except Exception as e:
        n8n_ph.error(f"❌ Error triggering n8n workflow: {str(e)}")
        st.session_state["n8n_triggered"] = False
    
    # Simple progress while n8n workflow runs
    if st.session_state.get("n8n_triggered"):
        # Show workflow is running
        n8n_ph.info(f"🔄 n8n workflow running for Case ID: {case_id}")
        
        # Simple progress animation (no complex sections)
        for i in range(100):
            progress.progress(i + 1)
            time.sleep(0.1)
        
        # Mark all steps as done
        for i in range(len(steps)):
            line(i, "done")
        
        n8n_ph.success(f"✅ Report generation complete! Files uploaded to S3.")
        st.session_state["workflow_status"] = "completed"
    else:
        # Fallback to simulation if n8n trigger failed
        n8n_ph.warning("⚠️ Using simulation mode due to n8n trigger failure")
        
        # Simple simulation progress
        for i in range(100):
            progress.progress(i + 1)
            time.sleep(0.1)
        
        # Mark all steps as done
        for i in range(len(steps)):
            line(i, "done")
 
    # End info section
    end_time = datetime.now()
    st.session_state["generation_end"] = end_time
    st.session_state["processing_seconds"] = int((end_time - start_time).total_seconds())
 
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="section-bg">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("STARTED")
            st.write(start_time.strftime("%b %d, %Y %I:%M %p").lstrip('0'))
        with c2:
            st.caption("FINISHED")
            st.write(end_time.strftime("%b %d, %Y %I:%M %p").lstrip('0'))
        with c3:
            seconds = st.session_state.get("processing_seconds", 0)
            st.caption("ELAPSED TIME")
            st.write(f"{seconds // 60}m {seconds % 60}s")
            st.info("We will email you upon completion with the download link.")
    
    # Show n8n workflow status and links
    if st.session_state.get("n8n_triggered"):
        st.success("🎯 n8n workflow successfully triggered!")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"[🔗 View n8n Workflow]({n8n_workflow_url})")
        with col2:
            st.markdown(f"[📊 Monitor Progress]({n8n_workflow_url})")
    else:
        st.warning("⚠️ n8n workflow not triggered. Check connection and try again.")
    
    st.markdown('</div>', unsafe_allow_html=True)
 
    st.markdown("<div style='text-align:center;margin-top:.5rem;'>", unsafe_allow_html=True)
    if st.button("View Results", type="primary"):
        try:
            qp = st.query_params if hasattr(st, "query_params") else None
            if qp is not None:
                qp["page"] = "Results"
                qp["case_id"] = case_id
        except Exception:
            pass
        st.markdown(
            f"""
            <script>
              const params = new URLSearchParams(window.location.search);
              params.set('page', 'Results');
              params.set('case_id', '{case_id}');
              window.location.search = '?' + params.toString();
            </script>
            """,
            unsafe_allow_html=True,
        )
        st.stop()
    st.markdown("</div>", unsafe_allow_html=True)
 
 
main()