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
        """Generate a polished PDF comparison report using ReportLab."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Flowable
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.colors import HexColor, black, white
            from reportlab.pdfgen import canvas as _canvas

            buffer = io.BytesIO()

            # Margins and document
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=0.75 * inch,
                rightMargin=0.75 * inch,
                topMargin=0.9 * inch,
                bottomMargin=0.9 * inch,
            )

            styles = getSampleStyleSheet()
            # Custom styles
            title_style = ParagraphStyle(
                'TitleXL', parent=styles['Heading1'], fontSize=24, leading=28,
                textColor=HexColor('#1f2937'), alignment=TA_CENTER, spaceAfter=10,
            )
            subtitle_style = ParagraphStyle(
                'Subtitle', parent=styles['Normal'], fontSize=12, leading=16,
                textColor=HexColor('#6b7280'), alignment=TA_CENTER, spaceAfter=6,
            )
            h2_style = ParagraphStyle(
                'H2', parent=styles['Heading2'], textColor=HexColor('#374151'), spaceBefore=6, spaceAfter=6
            )
            body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10.5, leading=14)

            # Header/Footer draw functions
            def _header_footer(c: _canvas.Canvas, doc_obj):
                w, h = A4
                # Header line and title
                c.setStrokeColor(HexColor('#e5e7eb'))
                c.line(0.75 * inch, h - 0.8 * inch, w - 0.75 * inch, h - 0.8 * inch)
                c.setFont('Helvetica', 9)
                c.setFillColor(HexColor('#6b7280'))
                c.drawString(0.75 * inch, h - 0.65 * inch, 'LCP Version Comparison Report')
                # Footer line and page number
                c.setStrokeColor(HexColor('#e5e7eb'))
                c.line(0.75 * inch, 0.8 * inch, w - 0.75 * inch, 0.8 * inch)
                c.setFont('Helvetica', 9)
                c.setFillColor(HexColor('#6b7280'))
                c.drawRightString(w - 0.75 * inch, 0.55 * inch, f"Page {doc_obj.page}")

            story = []

            # Cover page
            story.append(Spacer(1, 0.5 * inch))
            story.append(Paragraph('LCP Version Comparison', title_style))
            story.append(Paragraph('Section-by-Section Change Analysis', subtitle_style))
            story.append(Spacer(1, 0.25 * inch))

            # Tag bar
            tag_bg = HexColor('#eef2ff')
            class TagBar(Flowable):
                def __init__(self, text: str):
                    super().__init__()
                    self.text = text
                def draw(self):
                    c = self.canv
                    w = doc.width
                    c.setFillColor(tag_bg)
                    c.roundRect(0, 0, w, 18, 4, fill=1, stroke=0)
                    c.setFillColor(HexColor('#4f46e5'))
                    c.setFont('Helvetica-Bold', 10)
                    c.drawString(6, 5, self.text)

            meta_items = [
                f"Case ID: {results.get('case_id', '—')}",
                f"Mode: {str(results.get('mode', '—')).title()}",
                f"Generated: {results.get('comparison_timestamp', '—')}",
                f"Versions: {', '.join(results.get('versions_compared', []))}",
            ]
            for m in meta_items:
                story.append(TagBar(m))
                story.append(Spacer(1, 0.12 * inch))

            # Quick summary counts
            sections = results.get('sections', {})
            def _count(section_data):
                totals = {'total': 0, 'added': 0, 'removed': 0, 'modified': 0}
                def walk(d):
                    if isinstance(d, dict):
                        if 'status' in d:
                            totals['total'] += 1
                            s = d.get('status')
                            if s in totals:
                                totals[s] += 1
                        else:
                            for v in d.values():
                                walk(v)
                walk(section_data)
                return totals
            counts = _count(sections)
            story.append(Spacer(1, 0.15 * inch))
            story.append(Paragraph(
                f"<b>Summary:</b> Total Sections: {counts['total']} · Added: {counts['added']} · Removed: {counts['removed']} · Modified: {counts['modified']}",
                body_style,
            ))

            # New page for details
            story.append(PageBreak())

            # Detail sections
            for section_name, section_data in sections.items():
                if isinstance(section_data, dict) and 'status' in section_data:
                    story.extend(self._format_section_pdf(section_name, section_data, styles))
                else:
                    # Group heading for pairwise comparison
                    story.append(Paragraph(section_name, h2_style))
                    story.append(Spacer(1, 0.08 * inch))
                    for subsection_name, subsection_data in section_data.items():
                        story.extend(self._format_section_pdf(subsection_name, subsection_data, styles))

            doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
            return buffer.getvalue()

        except ImportError:
            raise ImportError("Please install reportlab: pip install reportlab")
    
    def _format_section_pdf(self, section_name: str, section_data: Dict, styles) -> List:
        """Format a single section for PDF report with colored status chips and spacing."""
        from reportlab.platypus import Paragraph, Spacer, Flowable
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor

        elements = []
        status = section_data.get('status', 'unknown')

        # Status chip
        chip_colors = {
            'added': ('#16a34a', '#dcfce7'),      # green
            'removed': ('#dc2626', '#fee2e2'),    # red
            'modified': ('#d97706', '#fef3c7'),   # amber
            'unchanged': ('#0ea5e9', '#e0f2fe'),  # sky
        }
        fg, bg = chip_colors.get(status, ('#6b7280', '#f3f4f6'))

        class StatusChip(Flowable):
            def __init__(self, text: str, fg_hex: str, bg_hex: str):
                super().__init__()
                self.text = text
                self.fg = HexColor(fg_hex)
                self.bg = HexColor(bg_hex)
                self.height = 16
            def draw(self):
                c = self.canv
                w = c.stringWidth(self.text, 'Helvetica-Bold', 9) + 12
                c.setFillColor(self.bg)
                c.roundRect(0, 0, w, self.height, 6, fill=1, stroke=0)
                c.setFillColor(self.fg)
                c.setFont('Helvetica-Bold', 9)
                c.drawString(6, 4, self.text)
                self.width = w

        # Title + chip
        elements.append(Paragraph(f"<b>{section_name}</b>", styles['Heading2']))
        elements.append(StatusChip(status.upper(), fg, bg))
        elements.append(Spacer(1, 0.06 * inch))

        if status == 'added':
            elements.append(Paragraph("Section added in newer version.", styles['Normal']))
        elif status == 'removed':
            elements.append(Paragraph("Section removed from newer version.", styles['Normal']))
        elif status == 'unchanged':
            elements.append(Paragraph("No changes detected.", styles['Normal']))
        elif status == 'modified':
            changes = section_data.get('changes', {})
            if changes.get('added'):
                elements.append(Paragraph("<b>Added:</b>", styles['Normal']))
                for line in changes['added'][:6]:
                    elements.append(Paragraph(f"+ {line}", styles['Normal']))
                elements.append(Spacer(1, 0.04 * inch))
            if changes.get('removed'):
                elements.append(Paragraph("<b>Removed:</b>", styles['Normal']))
                for line in changes['removed'][:6]:
                    elements.append(Paragraph(f"- {line}", styles['Normal']))
                elements.append(Spacer(1, 0.04 * inch))
            if changes.get('changed'):
                elements.append(Paragraph("<b>Modified:</b>", styles['Normal']))
                for ch in changes['changed'][:4]:
                    elements.append(Paragraph(f"<b>Old:</b> {ch.get('old','')}", styles['Normal']))
                    elements.append(Paragraph(f"<b>New:</b> {ch.get('new','')}", styles['Normal']))
                    elements.append(Spacer(1, 0.02 * inch))

        elements.append(Spacer(1, 0.18 * inch))
        return elements
