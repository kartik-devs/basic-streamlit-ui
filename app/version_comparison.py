"""
LCP Document Version Comparison Module

This module handles comparison of LCP (Life Care Plan) documents across versions,
providing detailed section-by-section analysis of changes.
"""

import io
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import difflib
from collections import defaultdict


class LCPVersionComparator:
    """Handles comparison of LCP document versions."""
    
    def __init__(self, s3_manager):
        """Initialize with S3 manager for document access."""
        self.s3_manager = s3_manager
        
    def get_lcp_versions(self, case_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all LCP documents for a case from S3.
        
        Args:
            case_id: The case ID to fetch documents for
            
        Returns:
            List of dicts with version info: {
                'version': str,
                'timestamp': str,
                's3_key': str,
                'filename': str,
                'size': int
            }
        """
        if not self.s3_manager.s3_client:
            return []
        
        try:
            # List all objects in the case's Output folder
            response = self.s3_manager.s3_client.list_objects_v2(
                Bucket=self.s3_manager.bucket_name,
                Prefix=f"{case_id}/Output/"
            )
            
            files = response.get('Contents', [])
            versions = []
            
            # Pattern to match LCP documents
            # Matches: YYYYMMDDHHMM-{case_id}-CompleteAIGeneratedReport.pdf
            # or similar patterns with LCP in the name
            lcp_pattern = re.compile(
                rf'(\d{{12}})-{case_id}-(CompleteAIGeneratedReport|LCP|LifeCarePlan)',
                re.IGNORECASE
            )
            
            for file_obj in files:
                key = file_obj['Key']
                filename = key.split('/')[-1]
                
                # Check if this is an LCP document
                if (filename.endswith('.pdf') and 
                    (lcp_pattern.search(filename) or 
                     'CompleteAIGenerated' in filename or
                     'LCP' in filename)):
                    
                    # Extract timestamp/version from filename
                    timestamp_match = re.search(r'(\d{12})', filename)
                    if timestamp_match:
                        timestamp_str = timestamp_match.group(1)
                        # Parse timestamp: YYYYMMDDHHMM
                        try:
                            dt = datetime.strptime(timestamp_str, '%Y%m%d%H%M')
                            formatted_time = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            formatted_time = timestamp_str
                    else:
                        formatted_time = file_obj.get('LastModified', 'Unknown')
                        if hasattr(formatted_time, 'strftime'):
                            formatted_time = formatted_time.strftime('%Y-%m-%d %H:%M')
                    
                    versions.append({
                        'version': timestamp_str if timestamp_match else filename,
                        'timestamp': formatted_time,
                        's3_key': key,
                        'filename': filename,
                        'size': file_obj.get('Size', 0),
                        'last_modified': file_obj.get('LastModified')
                    })
            
            # Sort by timestamp (newest first)
            versions.sort(key=lambda x: x.get('last_modified', ''), reverse=True)
            
            return versions
            
        except Exception as e:
            print(f"Error fetching LCP versions: {e}")
            return []
    
    def extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """
        Extract text content from PDF bytes.
        
        Args:
            pdf_bytes: PDF file as bytes
            
        Returns:
            Extracted text content
        """
        try:
            import PyPDF2
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = []
            for page in pdf_reader.pages:
                text.append(page.extract_text())
            
            return '\n'.join(text)
        except ImportError:
            # Fallback to pdfplumber if PyPDF2 not available
            try:
                import pdfplumber
                pdf_file = io.BytesIO(pdf_bytes)
                text = []
                with pdfplumber.open(pdf_file) as pdf:
                    for page in pdf.pages:
                        text.append(page.extract_text() or '')
                return '\n'.join(text)
            except ImportError:
                raise ImportError("Please install PyPDF2 or pdfplumber: pip install PyPDF2 pdfplumber")
    
    def extract_sections(self, text: str) -> Dict[str, str]:
        """
        Extract sections from LCP document text.
        
        Looks for common section patterns like:
        - Section 1: Title
        - 1. Title
        - SECTION 1 - Title
        
        Args:
            text: Full document text
            
        Returns:
            Dict mapping section names to content
        """
        sections = {}
        
        # Common section patterns in LCP documents
        section_patterns = [
            r'(?:Section|SECTION)\s+(\d+)[:\-\s]+([^\n]+)',
            r'^(\d+)\.\s+([A-Z][^\n]+)',
            r'(?:Part|PART)\s+([IVX]+)[:\-\s]+([^\n]+)',
        ]
        
        lines = text.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line is a section header
            is_section = False
            for pattern in section_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    # Save previous section
                    if current_section:
                        sections[current_section] = '\n'.join(current_content)
                    
                    # Start new section
                    section_num = match.group(1)
                    section_title = match.group(2).strip()
                    current_section = f"Section {section_num}: {section_title}"
                    current_content = []
                    is_section = True
                    break
            
            if not is_section and current_section:
                current_content.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        # If no sections found, treat entire document as one section
        if not sections:
            sections['Full Document'] = text
        
        return sections
    
    def compare_texts(self, text1: str, text2: str) -> Dict[str, List[str]]:
        """
        Compare two text strings and identify changes.
        
        Args:
            text1: Original text
            text2: New text
            
        Returns:
            Dict with 'added', 'removed', 'changed' lists
        """
        lines1 = text1.split('\n')
        lines2 = text2.split('\n')
        
        differ = difflib.Differ()
        diff = list(differ.compare(lines1, lines2))
        
        added = []
        removed = []
        changed = []
        
        i = 0
        while i < len(diff):
            line = diff[i]
            
            if line.startswith('+ '):
                added.append(line[2:])
            elif line.startswith('- '):
                # Check if next line is an addition (indicates change)
                if i + 1 < len(diff) and diff[i + 1].startswith('+ '):
                    changed.append({
                        'old': line[2:],
                        'new': diff[i + 1][2:]
                    })
                    i += 1  # Skip next line
                else:
                    removed.append(line[2:])
            
            i += 1
        
        return {
            'added': added,
            'removed': removed,
            'changed': changed
        }
    
    def compare_versions(
        self,
        case_id: str,
        version_keys: List[str],
        mode: str = 'selective'
    ) -> Dict[str, Any]:
        """
        Compare multiple versions of LCP documents.
        
        Args:
            case_id: Case ID
            version_keys: List of S3 keys for versions to compare
            mode: 'all' (compare all versions) or 'selective' (compare selected)
            
        Returns:
            Comparison results with section-by-section analysis
        """
        if not version_keys:
            return {'error': 'No versions provided for comparison'}
        
        # Download all versions
        versions_data = []
        for key in version_keys:
            pdf_bytes = self.s3_manager.download_file(key)
            if pdf_bytes:
                try:
                    text = self.extract_text_from_pdf(pdf_bytes)
                    sections = self.extract_sections(text)
                    versions_data.append({
                        'key': key,
                        'filename': key.split('/')[-1],
                        'sections': sections,
                        'text': text
                    })
                except Exception as e:
                    print(f"Error processing {key}: {e}")
        
        if len(versions_data) < 2:
            return {'error': 'Need at least 2 valid versions to compare'}
        
        # Perform comparison
        results = {
            'case_id': case_id,
            'mode': mode,
            'versions_compared': [v['filename'] for v in versions_data],
            'comparison_timestamp': datetime.now().isoformat(),
            'sections': {}
        }
        
        if mode == 'all':
            # Compare each version with the previous one
            for i in range(1, len(versions_data)):
                prev_version = versions_data[i - 1]
                curr_version = versions_data[i]
                
                comparison_key = f"{prev_version['filename']} → {curr_version['filename']}"
                results['sections'][comparison_key] = self._compare_section_sets(
                    prev_version['sections'],
                    curr_version['sections']
                )
        else:
            # Selective: compare first with last
            first_version = versions_data[0]
            last_version = versions_data[-1]
            
            results['sections'] = self._compare_section_sets(
                first_version['sections'],
                last_version['sections']
            )
        
        return results
    
    def _compare_section_sets(
        self,
        sections1: Dict[str, str],
        sections2: Dict[str, str]
    ) -> Dict[str, Any]:
        """Compare two sets of sections."""
        comparison = {}
        
        # Get all unique section names
        all_sections = set(sections1.keys()) | set(sections2.keys())
        
        for section_name in sorted(all_sections):
            text1 = sections1.get(section_name, '')
            text2 = sections2.get(section_name, '')
            
            if not text1:
                comparison[section_name] = {
                    'status': 'added',
                    'content': text2
                }
            elif not text2:
                comparison[section_name] = {
                    'status': 'removed',
                    'content': text1
                }
            else:
                diff = self.compare_texts(text1, text2)
                if diff['added'] or diff['removed'] or diff['changed']:
                    comparison[section_name] = {
                        'status': 'modified',
                        'changes': diff
                    }
                else:
                    comparison[section_name] = {
                        'status': 'unchanged'
                    }
        
        return comparison
    
    def generate_comparison_report(
        self,
        comparison_results: Dict[str, Any],
        output_format: str = 'html'
    ) -> bytes:
        """
        Generate a formatted comparison report.
        
        Args:
            comparison_results: Results from compare_versions
            output_format: 'html' or 'pdf'
            
        Returns:
            Report as bytes
        """
        if output_format == 'html':
            return self._generate_html_report(comparison_results)
        elif output_format == 'pdf':
            return self._generate_pdf_report(comparison_results)
        else:
            raise ValueError(f"Unsupported format: {output_format}")
    
    def _generate_html_report(self, results: Dict[str, Any]) -> bytes:
        """Generate HTML comparison report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>LCP Version Comparison - Case {results.get('case_id', 'Unknown')}</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                }}
                .section {{
                    background: white;
                    padding: 20px;
                    margin-bottom: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .section-title {{
                    font-size: 1.3em;
                    font-weight: bold;
                    margin-bottom: 15px;
                    color: #333;
                    border-bottom: 2px solid #667eea;
                    padding-bottom: 10px;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 5px 12px;
                    border-radius: 20px;
                    font-size: 0.85em;
                    font-weight: bold;
                    margin-left: 10px;
                }}
                .status-added {{ background: #d4edda; color: #155724; }}
                .status-removed {{ background: #f8d7da; color: #721c24; }}
                .status-modified {{ background: #fff3cd; color: #856404; }}
                .status-unchanged {{ background: #d1ecf1; color: #0c5460; }}
                .change-item {{
                    margin: 10px 0;
                    padding: 10px;
                    border-left: 3px solid #ddd;
                    background: #f9f9f9;
                }}
                .added {{ border-left-color: #28a745; background: #d4edda; }}
                .removed {{ border-left-color: #dc3545; background: #f8d7da; }}
                .changed {{ border-left-color: #ffc107; background: #fff3cd; }}
                .change-label {{
                    font-weight: bold;
                    margin-bottom: 5px;
                }}
                .metadata {{
                    color: #666;
                    font-size: 0.9em;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 LCP Version Comparison Report</h1>
                <p><strong>Case ID:</strong> {results.get('case_id', 'Unknown')}</p>
                <p><strong>Comparison Mode:</strong> {results.get('mode', 'Unknown').title()}</p>
                <p><strong>Generated:</strong> {results.get('comparison_timestamp', 'Unknown')}</p>
                <p><strong>Versions Compared:</strong> {', '.join(results.get('versions_compared', []))}</p>
            </div>
        """
        
        sections = results.get('sections', {})
        
        if isinstance(sections, dict):
            for section_key, section_data in sections.items():
                if isinstance(section_data, dict) and 'status' in section_data:
                    # Single comparison
                    html += self._format_section_html(section_key, section_data)
                else:
                    # Multiple comparisons (all mode)
                    html += f"<h2 style='margin-top: 30px;'>{section_key}</h2>"
                    for subsection_name, subsection_data in section_data.items():
                        html += self._format_section_html(subsection_name, subsection_data)
        
        html += """
        </body>
        </html>
        """
        
        return html.encode('utf-8')
    
    def _format_section_html(self, section_name: str, section_data: Dict) -> str:
        """Format a single section for HTML report."""
        status = section_data.get('status', 'unknown')
        status_class = f"status-{status}"
        
        html = f"""
        <div class="section">
            <div class="section-title">
                {section_name}
                <span class="status-badge {status_class}">{status.upper()}</span>
            </div>
        """
        
        if status == 'unchanged':
            html += "<p>No changes detected in this section.</p>"
        elif status == 'added':
            html += f'<div class="change-item added"><div class="change-label">✅ Section Added</div></div>'
        elif status == 'removed':
            html += f'<div class="change-item removed"><div class="change-label">❌ Section Removed</div></div>'
        elif status == 'modified':
            changes = section_data.get('changes', {})
            
            if changes.get('added'):
                html += '<div class="change-item added"><div class="change-label">✅ Added Lines:</div>'
                for line in changes['added'][:10]:  # Limit to first 10
                    html += f"<p>{line}</p>"
                if len(changes['added']) > 10:
                    html += f"<p><em>... and {len(changes['added']) - 10} more lines</em></p>"
                html += '</div>'
            
            if changes.get('removed'):
                html += '<div class="change-item removed"><div class="change-label">❌ Removed Lines:</div>'
                for line in changes['removed'][:10]:
                    html += f"<p>{line}</p>"
                if len(changes['removed']) > 10:
                    html += f"<p><em>... and {len(changes['removed']) - 10} more lines</em></p>"
                html += '</div>'
            
            if changes.get('changed'):
                html += '<div class="change-item changed"><div class="change-label">🔄 Modified Lines:</div>'
                for change in changes['changed'][:10]:
                    html += f"<p><strong>Old:</strong> {change.get('old', '')}</p>"
                    html += f"<p><strong>New:</strong> {change.get('new', '')}</p>"
                    html += "<hr style='margin: 10px 0; border: none; border-top: 1px solid #ddd;'>"
                if len(changes['changed']) > 10:
                    html += f"<p><em>... and {len(changes['changed']) - 10} more changes</em></p>"
                html += '</div>'
        
        html += "</div>"
        return html
    
    def _generate_pdf_report(self, results: Dict[str, Any]) -> bytes:
        """Generate PDF comparison report using ReportLab."""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_LEFT, TA_CENTER
            from reportlab.lib.colors import HexColor
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=HexColor('#667eea'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            story.append(Paragraph("LCP Version Comparison Report", title_style))
            story.append(Spacer(1, 0.2 * inch))
            
            # Metadata
            meta_style = styles['Normal']
            story.append(Paragraph(f"<b>Case ID:</b> {results.get('case_id', 'Unknown')}", meta_style))
            story.append(Paragraph(f"<b>Mode:</b> {results.get('mode', 'Unknown').title()}", meta_style))
            story.append(Paragraph(f"<b>Generated:</b> {results.get('comparison_timestamp', 'Unknown')}", meta_style))
            story.append(Paragraph(f"<b>Versions:</b> {', '.join(results.get('versions_compared', []))}", meta_style))
            story.append(Spacer(1, 0.5 * inch))
            
            # Sections
            sections = results.get('sections', {})
            for section_name, section_data in sections.items():
                if isinstance(section_data, dict) and 'status' in section_data:
                    story.extend(self._format_section_pdf(section_name, section_data, styles))
                else:
                    # Multiple comparisons
                    for subsection_name, subsection_data in section_data.items():
                        story.extend(self._format_section_pdf(subsection_name, subsection_data, styles))
            
            doc.build(story)
            return buffer.getvalue()
            
        except ImportError:
            raise ImportError("Please install reportlab: pip install reportlab")
    
    def _format_section_pdf(self, section_name: str, section_data: Dict, styles) -> List:
        """Format a single section for PDF report."""
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.units import inch
        
        elements = []
        status = section_data.get('status', 'unknown')
        
        # Section title
        elements.append(Paragraph(f"<b>{section_name}</b> [{status.upper()}]", styles['Heading2']))
        elements.append(Spacer(1, 0.1 * inch))
        
        if status == 'modified':
            changes = section_data.get('changes', {})
            
            if changes.get('added'):
                elements.append(Paragraph("<b>Added:</b>", styles['Normal']))
                for line in changes['added'][:5]:
                    elements.append(Paragraph(f"+ {line}", styles['Normal']))
            
            if changes.get('removed'):
                elements.append(Paragraph("<b>Removed:</b>", styles['Normal']))
                for line in changes['removed'][:5]:
                    elements.append(Paragraph(f"- {line}", styles['Normal']))
        
        elements.append(Spacer(1, 0.2 * inch))
        return elements
