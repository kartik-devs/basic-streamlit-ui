"""
Version Comparison Page

Compare different versions of LCP documents for a case.
"""

import streamlit as st
import os
from datetime import datetime
import requests
from app.ui import inject_base_styles, theme_provider, top_nav
from app.auth import require_authentication, get_current_user
from app.s3_utils import get_s3_manager
from app.version_comparison import LCPVersionComparator

# Require authentication
require_authentication()


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def main():
    """Main function for version comparison page."""
    try:
        st.set_page_config(
            page_title="Version Comparison",
            page_icon="🔄",
            layout="wide"
        )
        theme_provider()
        inject_base_styles()
    except Exception:
        pass
    
    # Navigation
    top_nav(active="Version Comparison")
    
    # Page header
    st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="color: #667eea; margin-bottom: 0.5rem;">🔄 LCP Version Comparison</h1>
            <p style="color: #6b7280; font-size: 1.1rem;">
                Compare different versions of Life Care Plan documents to track changes
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Initialize S3 manager and comparator
    s3_manager = get_s3_manager()
    if not s3_manager.s3_client:
        st.error("❌ S3 connection not available. Please check your configuration.")
        return
    
    comparator = LCPVersionComparator(s3_manager)
    
    # Step 1: Case ID Input
    st.markdown("### 📋 Step 1: Select Case")
    
    col1, col2 = st.columns([2, 1])
    
    # Cached fetch of available cases using backend like Case Report, with S3 fallback
    @st.cache_data(ttl=120)
    def fetch_available_cases_cached() -> list[str]:
        backend = (os.getenv("BACKEND_BASE") or "http://localhost:8000").rstrip("/")
        try:
            res = requests.get(f"{backend}/s3/cases", timeout=6)
            if res.ok:
                data = res.json() or {}
                cases = data.get("cases", []) or []
                return cases
        except Exception:
            pass
        # Fallback to direct S3 listing
        try:
            return s3_manager.list_available_cases() or []
        except Exception:
            return []

    with col1:
        available_cases = fetch_available_cases_cached()
        case_id = st.selectbox(
            "Case ID",
            options=[""] + available_cases,
            index=0,
            placeholder="Select or type case ID (4 digits)",
            help="Choose a case to compare its LCP document versions"
        )
    
    with col2:
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        load_disabled = not bool(case_id)
        if st.button("🔍 Load Versions", type="primary", use_container_width=True, disabled=load_disabled):
            st.session_state['selected_case_id'] = case_id
            st.session_state['versions_loaded'] = True
            st.rerun()
    
    if not case_id:
        st.info("👆 Please enter or select a case ID to begin")
        return
    
    # Store case_id in session state
    if 'selected_case_id' not in st.session_state:
        st.session_state['selected_case_id'] = case_id
    
    # Step 2: Fetch and display versions
    st.markdown("---")
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;margin: 8px 0 14px 0;">
            <div style="width:8px;height:24px;border-radius:6px;background:linear-gradient(135deg,#6366f1,#22d3ee)"></div>
            <div style="font-size:1.25rem;font-weight:800;color:#e5e7eb;">Step 2: Select Versions to Compare</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    with st.spinner("Loading available versions..."):
        versions = comparator.get_lcp_versions(case_id)
    
    if not versions:
        st.warning(f"⚠️ No LCP document versions found for case {case_id}")
        st.info("Make sure the case has generated LCP reports in the Output folder.")
        return
    
    # Display version count banner
    st.markdown(
        f"""
        <div style="padding:12px 14px;border-radius:10px;border:1px solid rgba(99,102,241,0.25);
        background:linear-gradient(135deg,rgba(16,185,129,0.12),rgba(99,102,241,0.10));color:#d1fae5;">
            <span style="font-weight:700;color:#34d399;">Found {len(versions)} version(s)</span>
            <span style="color:#9ca3af;"> for case </span>
            <span style="font-weight:700;color:#e5e7eb;">{case_id}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Comparison mode with tabs
    st.markdown(
        """
        <div style="margin-top:12px;margin-bottom:6px;font-weight:700;color:#cbd5e1;">Comparison Mode</div>
        """,
        unsafe_allow_html=True,
    )
    tab_selective, tab_overall = st.tabs(["🎯 Selective", "📊 Overall"])
    
    selected_versions = []
    
    with tab_selective:
        st.markdown(
            """
            <div style="margin-top:6px;margin-bottom:8px;color:#9ca3af;">Choose at least 2 versions to compare</div>
            """,
            unsafe_allow_html=True,
        )
        # Create a grid layout for version cards
        cols_per_row = 3
        for i in range(0, len(versions), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(versions):
                    version = versions[idx]
                    with col:
                        # Native bordered container card
                        with st.container():
                            is_selected = st.toggle(
                                f"{version['filename'][:48]}..." if len(version['filename']) > 48 else f"{version['filename']}",
                                key=f"version_{idx}",
                                help=f"Full name: {version['filename']}"
                            )
                            if is_selected:
                                selected_versions.append(version['s3_key'])
                            st.caption(f"📅 {version['timestamp']}")
                            st.caption(f"📦 {format_file_size(version['size'])}")
                        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        # Update session state for selective mode when valid
        if len(selected_versions) >= 2:
            st.session_state['selected_versions'] = selected_versions
            st.session_state['comparison_mode'] = 'selective'
            st.success(f"✅ Selected {len(selected_versions)} versions for comparison")
        else:
            st.info("ℹ️ Please select at least 2 versions to compare")
    
    with tab_overall:
        st.markdown("#### Compare All Versions")
        # Modern active container
        st.markdown(f"""
        <div style="
            padding: 16px 18px; 
            border-radius: 10px; 
            border: 1px solid #e5e7eb; 
            background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(59,130,246,0.06));
            display: flex; align-items: center; gap: 12px;">
            <div style="
                background:#eef2ff; color:#4f46e5; 
                padding: 6px 10px; border-radius: 999px; 
                font-weight: 700; font-size: 12px;">
                OVERALL MODE
            </div>
            <div style="color:#374151; font-weight:600;">All versions will be compared sequentially (newest to oldest).</div>
        </div>
        """, unsafe_allow_html=True)

        # Auto-activate overall mode without a checkbox, but do not override a valid selective selection
        all_version_keys = [v['s3_key'] for v in versions]
        has_valid_selective = (
            st.session_state.get('comparison_mode') == 'selective' and 
            isinstance(st.session_state.get('selected_versions'), list) and 
            len(st.session_state.get('selected_versions')) >= 2
        )
        if not has_valid_selective:
            st.session_state['selected_versions'] = all_version_keys
            st.session_state['comparison_mode'] = 'all'
    
    # Step 3: Run comparison
    st.markdown("---")
    st.markdown("### 🔄 Step 3: Generate Comparison Report")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        output_format = st.selectbox(
            "Output Format",
            options=['html', 'pdf'],
            format_func=lambda x: {
                'html': '🌐 HTML (Interactive)',
                'pdf': '📄 PDF (Printable)'
            }[x]
        )
    
    with col2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🚀 Generate Comparison", type="primary", use_container_width=True):
            st.session_state['run_comparison'] = True
            st.rerun()
    
    with col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 Reset", use_container_width=True):
            # Clear session state
            for key in ['selected_case_id', 'selected_versions', 'run_comparison', 'comparison_results']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # Run comparison if triggered
    if st.session_state.get('run_comparison', False):
        st.markdown("---")
        
        with st.spinner("🔄 Comparing versions... This may take a moment..."):
            try:
                # Perform comparison
                # Resolve mode and versions from session state (set by tabs above)
                mode_effective = st.session_state.get('comparison_mode') or 'selective'
                versions_effective = st.session_state.get('selected_versions') or []
                comparison_results = comparator.compare_versions(
                    case_id=case_id,
                    version_keys=versions_effective,
                    mode=mode_effective
                )
                
                # Check for errors
                if 'error' in comparison_results:
                    st.error(f"❌ Comparison failed: {comparison_results['error']}")
                    return
                
                # Store results
                st.session_state['comparison_results'] = comparison_results
                
                # Generate report
                report_bytes = comparator.generate_comparison_report(
                    comparison_results,
                    output_format=output_format
                )
                
                st.session_state['report_bytes'] = report_bytes
                st.session_state['report_format'] = output_format
                
                st.success("✅ Comparison completed successfully!")
                
            except Exception as e:
                st.error(f"❌ Error during comparison: {str(e)}")
                st.exception(e)
                return
    
    # Display results
    if 'comparison_results' in st.session_state and 'report_bytes' in st.session_state:
        st.markdown("---")
        st.markdown("### 📊 Comparison Results")
        
        results = st.session_state['comparison_results']
        report_bytes = st.session_state['report_bytes']
        report_format = st.session_state['report_format']
        
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        sections = results.get('sections', {})
        total_sections = 0
        added_sections = 0
        removed_sections = 0
        modified_sections = 0
        
        # Count section statuses
        def count_sections(section_data):
            nonlocal total_sections, added_sections, removed_sections, modified_sections
            if isinstance(section_data, dict):
                if 'status' in section_data:
                    total_sections += 1
                    status = section_data['status']
                    if status == 'added':
                        added_sections += 1
                    elif status == 'removed':
                        removed_sections += 1
                    elif status == 'modified':
                        modified_sections += 1
                else:
                    for subsection in section_data.values():
                        count_sections(subsection)
        
        count_sections(sections)
        
        with col1:
            st.metric("Total Sections", total_sections)
        with col2:
            st.metric("Added", added_sections, delta=added_sections if added_sections > 0 else None)
        with col3:
            st.metric("Removed", removed_sections, delta=-removed_sections if removed_sections > 0 else None)
        with col4:
            st.metric("Modified", modified_sections, delta=modified_sections if modified_sections > 0 else None)
        
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        
        # Download button
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"lcp_comparison_{case_id}_{timestamp}.{report_format}"
        
        st.download_button(
            label=f"📥 Download {report_format.upper()} Report",
            data=report_bytes,
            file_name=filename,
            mime='text/html' if report_format == 'html' else 'application/pdf',
            type="primary",
            use_container_width=True
        )
        
        # Display preview
        st.markdown("#### 👁️ Report Preview")
        
        if report_format == 'html':
            # Display HTML in iframe
            import base64
            b64 = base64.b64encode(report_bytes).decode()
            iframe_html = f'<iframe src="data:text/html;base64,{b64}" width="100%" height="1100" style="border: 1px solid #ddd; border-radius: 8px;"></iframe>'
            st.markdown(iframe_html, unsafe_allow_html=True)
        else:
            # Display PDF
            import base64
            b64 = base64.b64encode(report_bytes).decode()
            iframe_pdf = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="1100" style="border: 1px solid #ddd; border-radius: 8px;"></iframe>'
            st.markdown(iframe_pdf, unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown("""
        <div style="text-align: center; color: #6b7280; font-size: 0.9rem; padding: 20px;">
            <p>💡 <strong>Tip:</strong> Use selective comparison to focus on specific versions, or overall comparison to see the evolution of the document.</p>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
