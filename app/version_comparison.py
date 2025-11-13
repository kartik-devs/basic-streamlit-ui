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
        # Canonical top-level ToC (10 sections). All extraction will be mapped to these.
        self.top_toc = [
            { 'id': '1',  'label': 'Overview' },
            { 'id': '2',  'label': 'Life Care Planning and Life Care Plans' },
            { 'id': '3',  'label': 'Biography of Medical Expert' },
            { 'id': '4',  'label': 'Framework: A Life Care Plan for Fatima Dodson' },
            { 'id': '5',  'label': 'Summary of Records' },
            { 'id': '6',  'label': 'Interview' },
            { 'id': '7',  'label': 'Central Opinions' },
            { 'id': '8',  'label': 'Future Medical Requirements' },
            { 'id': '9',  'label': 'Cost/Vendor Survey' },
            { 'id': '10', 'label': 'Overview of Medical Expert' },
        ]
        # Precompute normalized labels
        self._toc_norm = [(t['id'], t['label'], self._norm_heading(t['label'])) for t in self.top_toc]
        # Canonical level-2 ToC (select common sub-sections). This is extensible.
        self.level2_toc = [
            { 'id': '1.1', 'top_id': '1', 'label': 'Executive Summary' },
            { 'id': '1.2', 'top_id': '1', 'label': 'Life Care Planning and Life Care Plans' },
            { 'id': '2.1', 'top_id': '2', 'label': 'Summary of Medical Records' },
            { 'id': '6.1', 'top_id': '6', 'label': 'Recent History' },
            { 'id': '6.2', 'top_id': '6', 'label': 'Review of Systems' },
        ]
        self._l2_norm = [(t['id'], t['top_id'], t['label'], self._norm_heading(t['label'])) for t in self.level2_toc]
        
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

    def _extract_page_texts(self, pdf_bytes: bytes) -> List[str]:
        """Extract text per page for page number inference."""
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or '')
            return pages
        except Exception:
            try:
                import pdfplumber
                pages = []
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    for page in pdf.pages:
                        pages.append(page.extract_text() or '')
                return pages
            except Exception:
                return []
    
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
        
        # Common section patterns in LCP documents (support hierarchical and flat numbering)
        section_patterns = [
            r'^(?:Section|SECTION)\s+(\d+(?:\.\d+)*)[\s:\-\.\)]*([^\n]+)',
            r'^(\d+(?:\.\d+)*)(?:[\.)])?\s+([A-Z][^\n]+)',
            r'^(?:Part|PART)\s+([IVX]+)[\s:\-\.\)]*([^\n]+)',
        ]
        
        lines = text.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Ignore table captions and bullets/numbered list lines that aren't headings
            if re.match(r'^Table\s+\d+\s*:', line, re.IGNORECASE):
                continue
            if re.match(r'^[-•\*]\s+', line):
                if current_section:
                    current_content.append(line)
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
                    # Prefer level-2 mapping when available
                    l2_mapped = self._map_to_level2(section_title)
                    if l2_mapped:
                        l2_id, l2_label, top_id = l2_mapped
                        current_section = f"{l2_id} {l2_label}"
                        current_content = []
                        is_section = True
                        break
                    # Otherwise map to canonical top-level ToC; if no good match, skip as non-top-level
                    mapped = self._map_to_top_toc(section_title)
                    if mapped:
                        toc_id, toc_label = mapped
                        current_section = f"{toc_id}. {toc_label}"
                        current_content = []
                        is_section = True
                        break
                    else:
                        # Not a recognized section; treat as content under current_section (if any)
                        is_section = False
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

    def _infer_section_pages(self, page_texts: List[str]) -> Dict[str, int]:
        """Infer first page for each top-level ToC section (1-indexed)."""
        if not page_texts:
            return {}
        pages_map: Dict[str, int] = {}
        section_header_regexes = [
            re.compile(r'^(?:Section|SECTION)\s+(\d+(?:\.\d+)*)[\s:\-\.\)]*([^\n]+)', re.IGNORECASE),
            re.compile(r'^(\d+(?:\.\d+)*)(?:[\.)])?\s+([A-Z][^\n]+)', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^(?:Part|PART)\s+([IVX]+)[\s:\-\.\)]*([^\n]+)', re.IGNORECASE),
        ]
        for idx, page_txt in enumerate(page_texts):
            if not page_txt:
                continue
            for line in page_txt.split('\n'):
                line_s = line.strip()
                # Ignore table captions
                if re.match(r'^Table\s+\d+\s*:', line_s, re.IGNORECASE):
                    continue
                for rgx in section_header_regexes:
                    m = rgx.match(line_s)
                    if m:
                        title = m.group(2).strip()
                        # Prefer level-2 mapping when available
                        l2_mapped = self._map_to_level2(title)
                        if l2_mapped:
                            l2_id, l2_label, _top = l2_mapped
                            name = f"{l2_id} {l2_label}"
                            if name not in pages_map:
                                pages_map[name] = idx + 1
                        else:
                            mapped = self._map_to_top_toc(title)
                            if mapped:
                                toc_id, toc_label = mapped
                                name = f"{toc_id}. {toc_label}"
                                if name not in pages_map:
                                    pages_map[name] = idx + 1  # 1-indexed
                        break
        return pages_map

    def _norm_heading(self, s: str) -> str:
        s = s.replace('&', ' and ')
        return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', s.lower())).strip()

    def _norm_tokens(self, s: str) -> List[str]:
        base = self._norm_heading(s)
        toks = [t for t in base.split(' ') if t]
        # naive singularization: drop trailing 's' for longer tokens
        norm = [t[:-1] if len(t) > 4 and t.endswith('s') else t for t in toks]
        return norm

    def _map_to_top_toc(self, heading: str, threshold: float = 0.6) -> Optional[Tuple[str, str]]:
        """Map a heading to the closest top-level ToC entry using robust similarity."""
        from difflib import SequenceMatcher
        h = self._norm_heading(heading)
        h_toks = set(self._norm_tokens(heading))
        best_score = 0.0
        best_pair = None
        for tid, label, norm in self._toc_norm:
            # string ratio
            sm = SequenceMatcher(None, h, norm).ratio()
            # token overlap (Jaccard)
            l_toks = set(self._norm_tokens(label))
            inter = len(h_toks & l_toks)
            union = len(h_toks | l_toks) or 1
            jacc = inter / union
            # substring bonus
            contains = 1.0 if (norm in h or h in norm) else 0.0
            score = max(sm, jacc, contains)
            if score > best_score:
                best_score = score
                best_pair = (tid, label)
        return best_pair if best_score >= threshold else None

    def _map_to_level2(self, heading: str, threshold: float = 0.65) -> Optional[Tuple[str, str, str]]:
        """Map a heading to the closest level-2 ToC entry (returns id, label, top_id)."""
        from difflib import SequenceMatcher
        h = self._norm_heading(heading)
        h_toks = set(self._norm_tokens(heading))
        best_score = 0.0
        best = None
        for l2_id, top_id, label, norm in self._l2_norm:
            sm = SequenceMatcher(None, h, norm).ratio()
            l_toks = set(self._norm_tokens(label))
            inter = len(h_toks & l_toks)
            union = len(h_toks | l_toks) or 1
            jacc = inter / union
            contains = 1.0 if (norm in h or h in norm) else 0.0
            score = max(sm, jacc, contains)
            if score > best_score:
                best_score = score
                best = (l2_id, label, top_id)
        return best if best_score >= threshold else None

    def _toc_sort_key(self, key: str) -> Tuple:
        """Sort by hierarchical numeric id prefix: '1', '1.1', '10', etc."""
        m = re.match(r'^(\d+(?:\.\d+)*)\s', key)
        if not m:
            return (9999,)
        parts = m.group(1).split('.')
        try:
            return tuple(int(p) for p in parts)
        except Exception:
            return (9999,)
    
    def compare_texts(self, text1: str, text2: str) -> Dict[str, List[str]]:
        """
        Compare two text strings and identify changes.
        
        Args:
            text1: Original text
            text2: New text
            
        Returns:
            Dict with 'added', 'removed', 'changed' lists
        """
        # Normalize (preserve newlines) and split into line-aware sentences
        n1 = self._normalize_text(text1)
        n2 = self._normalize_text(text2)
        lines1 = self._split_sentences(n1)
        lines2 = self._split_sentences(n2)
        
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
        
        # Fallback: if nothing detected but texts differ, do a raw line-based diff
        if not (added or removed or changed) and (n1.strip() != n2.strip()):
            raw1 = [ln for ln in n1.split('\n') if ln.strip()]
            raw2 = [ln for ln in n2.split('\n') if ln.strip()]
            diff2 = list(difflib.Differ().compare(raw1, raw2))
            i = 0
            while i < len(diff2):
                line = diff2[i]
                if line.startswith('+ '):
                    added.append(line[2:])
                elif line.startswith('- '):
                    if i + 1 < len(diff2) and diff2[i + 1].startswith('+ '):
                        changed.append({'old': line[2:], 'new': diff2[i + 1][2:]})
                        i += 1
                    else:
                        removed.append(line[2:])
                i += 1

        # Numeric-aware diff: build label->amount maps and compare
        num1 = self._extract_numeric_map(n1)
        num2 = self._extract_numeric_map(n2)
        num_changed = []
        num_added = []
        num_removed = []
        for label in set(num1.keys()) | set(num2.keys()):
            v1 = num1.get(label)
            v2 = num2.get(label)
            if v1 is None and v2 is not None:
                num_added.append({'label': label, 'new': v2})
            elif v2 is None and v1 is not None:
                num_removed.append({'label': label, 'old': v1})
            elif v1 is not None and v2 is not None and abs(v1 - v2) > 0.01:
                num_changed.append({'label': label, 'old': v1, 'new': v2, 'delta': v2 - v1})

        return {
            'added': added,
            'removed': removed,
            'changed': changed,
            'numeric': {
                'changed': num_changed,
                'added': num_added,
                'removed': num_removed,
            }
        }

    def _normalize_text(self, text: str) -> str:
        """Normalize PDF-extracted text to improve diff quality while preserving line breaks."""
        if not text:
            return ''
        t = text
        # Remove common headers/footers
        t = re.sub(r'^\s*LCP Version Comparison Report\s*$', '', t, flags=re.MULTILINE)
        t = re.sub(r'^\s*Page\s+\d+\s*$', '', t, flags=re.MULTILINE)
        # Normalize quotes/dashes/spaces
        t = t.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
        t = t.replace('\u2013', '-').replace('\u2014', '-')
        # Collapse spaces/tabs but keep newlines (tables rely on line boundaries)
        t = re.sub(r'[ \t]+', ' ', t)
        # Fix spaced punctuation (e.g., "year -old")
        t = re.sub(r'\s-\s', '-', t)
        # Keep sentence endings clear
        return t.strip()

    def _split_sentences(self, text: str) -> List[str]:
        """Line-aware sentence splitter: keeps table rows/bullets as units."""
        if not text:
            return []
        units: List[str] = []
        for ln in text.split('\n'):
            s = ln.strip()
            if not s:
                continue
            # Treat bullets, numbered items, and table-like lines as atomic units
            if re.match(r'^(?:[-•\*]|\d+\.|\d+\))\s+', s) or \
               re.search(r'\$\s*\d', s) or \
               re.match(r'^(?:Table|Start Year|End Year|Years|Frequency Per Year|Cost per Item|Annual Cost|Lifetime Cost|Total)\b', s, re.IGNORECASE):
                units.append(s)
                continue
            # Otherwise split into sentences within the line
            parts = re.split(r'(?<=[\.!\?])\s+(?=[A-Z0-9])', s)
            if len(parts) < 2:
                parts = re.split(r'(?<=[\.;:])\s+', s)
            for p in parts:
                p = p.strip()
                if p:
                    units.append(p)
        return units

    def _parse_amount(self, s: str) -> Optional[float]:
        s2 = s.replace('$', '').replace(',', '').strip()
        try:
            return float(s2)
        except Exception:
            return None

    def _extract_numeric_map(self, text: str) -> Dict[str, float]:
        """Extract mapping of row labels -> numeric amount from lines ending with a currency/number.
        This helps catch changes in tables like Summary Cost Projection Tables.
        """
        mapping: Dict[str, float] = {}
        if not text:
            return mapping
        for ln in text.split('\n'):
            s = ln.strip()
            if not s:
                continue
            m = re.search(r'(\$?\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*$', s)
            if not m:
                continue
            amt = self._parse_amount(m.group(1))
            if amt is None:
                continue
            label = re.sub(r'(\$?\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*$', '', s).strip()
            # remove leading table/index tokens
            label = re.sub(r'^(?:table\s+\d+\s*[:\.]?)\s*', '', label, flags=re.IGNORECASE)
            label = re.sub(r'^\d+(?:\.\d+)*\s*', '', label)
            label = re.sub(r'\s{2,}', ' ', label)
            label = self._norm_heading(label)
            if not label:
                continue
            mapping[label] = amt
        return mapping
    
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
                    pages = self._extract_page_texts(pdf_bytes)
                    sections = self.extract_sections(text)
                    section_pages = self._infer_section_pages(pages)
                    # Try to parse timestamp from filename to establish chronological order
                    fname = key.split('/')[-1]
                    dt_val = None
                    ts_match = re.search(r'(\d{12})', fname)
                    if ts_match:
                        try:
                            dt_val = datetime.strptime(ts_match.group(1), '%Y%m%d%H%M')
                        except Exception:
                            dt_val = None
                    versions_data.append({
                        'key': key,
                        'filename': fname,
                        'sections': sections,
                        'text': text,
                        'section_pages': section_pages,
                        'dt': dt_val
                    })
                except Exception as e:
                    print(f"Error processing {key}: {e}")
        
        if len(versions_data) < 2:
            return {'error': 'Need at least 2 valid versions to compare'}
        
        # Sort by time ascending (older -> newer) when timestamps are available
        def _sort_key(v):
            return v.get('dt') or datetime.min
        versions_data.sort(key=_sort_key)

        # Perform comparison
        results = {
            'case_id': case_id,
            'mode': mode,
            'versions_compared': [v['filename'] for v in versions_data],
            'comparison_timestamp': datetime.now().isoformat(),
            'sections': {}
        }
        
        if mode == 'all':
            # Compare each version with the next newer one (chronological order)
            for i in range(1, len(versions_data)):
                prev_version = versions_data[i - 1]
                curr_version = versions_data[i]
                
                comparison_key = f"{prev_version['filename']} → {curr_version['filename']}"
                results['sections'][comparison_key] = self._compare_section_sets(
                    prev_version['sections'],
                    curr_version['sections'],
                    prev_version.get('section_pages', {}),
                    curr_version.get('section_pages', {})
                )
        else:
            # Selective: compare oldest with newest
            first_version = versions_data[0]  # oldest
            last_version = versions_data[-1]  # newest
            
            results['sections'] = self._compare_section_sets(
                first_version['sections'],
                last_version['sections'],
                first_version.get('section_pages', {}),
                last_version.get('section_pages', {})
            )
        
        return results
    
    def _compare_section_sets(
        self,
        sections1: Dict[str, str],
        sections2: Dict[str, str],
        pages1: Dict[str, int],
        pages2: Dict[str, int],
    ) -> Dict[str, Any]:
        """Compare two sets of sections and attach page numbers when available."""
        comparison = {}
        
        # Compare canonical keys only (top-level and level-2): "<id[.id] ...> <label>"
        all_sections = set(sections1.keys()) | set(sections2.keys())
        def _is_canonical(k: str) -> bool:
            return bool(re.match(r'^\d+(?:\.\d+)*\s', k))
        all_sections = {k for k in all_sections if _is_canonical(k)}
        
        for section_name in sorted(all_sections, key=self._toc_sort_key):
            text1 = sections1.get(section_name, '')
            text2 = sections2.get(section_name, '')
            
            if not text1:
                comparison[section_name] = {
                    'status': 'added',
                    'content': text2,
                    'pages': {'old': None, 'new': pages2.get(section_name)}
                }
            elif not text2:
                comparison[section_name] = {
                    'status': 'removed',
                    'content': text1,
                    'pages': {'old': pages1.get(section_name), 'new': None}
                }
            else:
                diff = self.compare_texts(text1, text2)
                has_num = bool(diff.get('numeric', {}).get('changed') or diff.get('numeric', {}).get('added') or diff.get('numeric', {}).get('removed'))
                if diff['added'] or diff['removed'] or diff['changed'] or has_num:
                    entry = {
                        'status': 'modified',
                        'changes': diff,
                        'pages': {'old': pages1.get(section_name), 'new': pages2.get(section_name)}
                    }
                    if self._is_tables_section(section_name):
                        entry['old_content'] = text1
                        entry['new_content'] = text2
                    comparison[section_name] = entry
                else:
                    comparison[section_name] = {
                        'status': 'unchanged',
                        'pages': {'old': pages1.get(section_name), 'new': pages2.get(section_name)}
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
            for section_name in sorted(sections.keys(), key=self._toc_sort_key):
                section_data = sections[section_name]
                if isinstance(section_data, dict) and 'status' in section_data:
                    # Single comparison
                    html += self._format_section_html(section_name, section_data)
                else:
                    # Multiple comparisons (all mode)
                    html += f"<h2 style='margin-top: 30px;'>{section_name}</h2>"
                    for subsection_name in sorted(section_data.keys(), key=self._toc_sort_key):
                        subsection_data = section_data[subsection_name]
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
        # Pages line if available
        pages = section_data.get('pages') if isinstance(section_data, dict) else None
        if isinstance(pages, dict):
            old_p = pages.get('old')
            new_p = pages.get('new')
            html += f"<div class='metadata'>Pages: {('old p'+str(old_p)) if old_p else 'old —'} → {('new p'+str(new_p)) if new_p else 'new —'}</div>"
        
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
            # Numeric table snapshots for Section 9 (tables)
            num = changes.get('numeric', {}) if isinstance(changes, dict) else {}
            if (num.get('changed') or num.get('added') or num.get('removed')) and self._is_tables_section(section_name):
                old_txt = section_data.get('old_content') or ''
                new_txt = section_data.get('new_content') or ''
                old_tables = self._extract_table_blocks(old_txt)
                new_tables = self._extract_table_blocks(new_txt)
                def _esc(x: str) -> str:
                    return x.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                if old_tables:
                    html += "<div class='change-item'><div class='change-label'>📄 Old Table Snapshot</div>"
                    html += f"<pre style='white-space: pre-wrap; background:#f6f8fa; padding:10px; border-radius:6px;'>{_esc('\n'.join(old_tables))}</pre></div>"
                if new_tables:
                    html += "<div class='change-item'><div class='change-label'>📄 New Table Snapshot</div>"
                    html += f"<pre style='white-space: pre-wrap; background:#f6f8fa; padding:10px; border-radius:6px;'>{_esc('\n'.join(new_tables))}</pre></div>"
        
        html += "</div>"
        return html
    
    def _generate_pdf_report(self, results: Dict[str, Any]) -> bytes:
        """Generate a polished PDF comparison report using ReportLab with improved readability."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, PageBreak, Flowable,
                ListFlowable, ListItem, Table, TableStyle, KeepTogether, Preformatted
            )
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.colors import HexColor
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
            h2_style = ParagraphStyle('H2', parent=styles['Heading2'], textColor=HexColor('#374151'), spaceBefore=6, spaceAfter=6)
            body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10.5, leading=14)
            mono_style = ParagraphStyle('Mono', parent=styles['Code'], fontName='Courier', fontSize=9.5, leading=12)

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
            story.append(Spacer(1, 0.3 * inch))

            # Metadata panel (table) with wrapping and bullet list for versions
            meta_rows = []
            meta_rows.append([Paragraph('<b>Case ID</b>', body_style), Paragraph(str(results.get('case_id', '—')), body_style)])
            mode_val = str(results.get('mode', '—')).title()
            meta_rows.append([Paragraph('<b>Mode</b>', body_style), Paragraph(mode_val, body_style)])
            meta_rows.append([Paragraph('<b>Generated</b>', body_style), Paragraph(str(results.get('comparison_timestamp', '—')), body_style)])

            versions = results.get('versions_compared', []) or []
            # Comparing row for clarity
            if mode_val.lower() == 'selective' and versions and len(versions) >= 2:
                meta_rows.append([Paragraph('<b>Comparing</b>', body_style), Paragraph(f"{versions[0]} → {versions[-1]}", body_style)])

            if versions:
                version_items = [ListItem(Paragraph(v, body_style)) for v in versions]
                versions_list = ListFlowable(version_items, bulletType='bullet', leftIndent=12)
            else:
                versions_list = Paragraph('—', body_style)

            meta_rows.append([Paragraph('<b>Versions</b>', body_style), versions_list])

            meta_tbl = Table(meta_rows, colWidths=[1.3 * inch, doc.width - 1.3 * inch])
            meta_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), HexColor('#f8fafc')),
                ('BOX', (0,0), (-1,-1), 0.8, HexColor('#e5e7eb')),
                ('INNERGRID', (0,0), (-1,-1), 0.3, HexColor('#e5e7eb')),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(meta_tbl)

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

            # Legend
            story.append(Spacer(1, 0.2 * inch))
            legend = [
                ('#16a34a', 'Added'),
                ('#dc2626', 'Removed'),
                ('#d97706', 'Modified'),
                ('#0ea5e9', 'Unchanged')
            ]
            legend_items = []
            for color_hex, label in legend:
                legend_items.append(Paragraph(f"<font color='{color_hex}'>■</font> {label}", body_style))
            legend_tbl = Table([legend_items])
            legend_tbl.setStyle(TableStyle([
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(legend_tbl)

            # New page for details
            story.append(PageBreak())

            # Detail sections
            for section_name in sorted(sections.keys(), key=self._toc_sort_key):
                section_data = sections[section_name]
                if isinstance(section_data, dict) and 'status' in section_data:
                    story.extend(self._format_section_pdf(section_name, section_data, styles))
                else:
                    # Group heading for pairwise comparison
                    story.append(Paragraph(section_name, h2_style))
                    story.append(Spacer(1, 0.08 * inch))
                    for subsection_name in sorted(section_data.keys(), key=self._toc_sort_key):
                        subsection_data = section_data[subsection_name]
                        story.extend(self._format_section_pdf(subsection_name, subsection_data, styles))

            doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
            return buffer.getvalue()

        except ImportError:
            raise ImportError("Please install reportlab: pip install reportlab")
    
    def _format_section_pdf(self, section_name: str, section_data: Dict, styles) -> List:
        """Format a single section for PDF with header + pages line and splittable body content."""
        from reportlab.platypus import Paragraph, Spacer, ListFlowable, ListItem, Table, TableStyle, Preformatted
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor

        elements = []
        status = section_data.get('status', 'unknown')

        chip_colors = {
            'added': ('#16a34a', '#dcfce7'),
            'removed': ('#dc2626', '#fee2e2'),
            'modified': ('#d97706', '#fef3c7'),
            'unchanged': ('#0ea5e9', '#e0f2fe'),
        }
        fg, bg = chip_colors.get(status, ('#6b7280', '#f3f4f6'))

        # Header row: title + status chip drawn as colored label (as small table)
        header = [
            Paragraph(f"<b>{section_name}</b>", styles['Heading3']),
            Paragraph(f"<font color='{fg}'><b>{status.upper()}</b></font>", styles['Normal'])
        ]

        # Build body content
        body_flow = []
        changes = section_data.get('changes', {}) if status == 'modified' else {}

        def _list(items, prefix):
            return ListFlowable(
                [ListItem(Paragraph(f"{prefix} {line}", styles['Normal'])) for line in items],
                bulletType='bullet', leftIndent=14, bulletFontName='Helvetica'
            )

        if status == 'added':
            body_flow.append(Paragraph("Section added in the newer version.", styles['Normal']))
        elif status == 'removed':
            body_flow.append(Paragraph("Present only in the older version (missing in newer).", styles['Normal']))
        elif status == 'unchanged':
            body_flow.append(Paragraph("No differences between the two compared versions.", styles['Normal']))
        elif status == 'modified':
            # Summary counts line
            add_n = len(changes.get('added', []))
            rem_n = len(changes.get('removed', []))
            chg_n = len(changes.get('changed', []))
            body_flow.append(Paragraph(f"<b>Change summary:</b> +{add_n} / -{rem_n} / ↔︎ {chg_n}", styles['Normal']))
            if changes.get('added'):
                body_flow.append(Spacer(1, 0.04 * inch))
                body_flow.append(Paragraph("<b>New lines (examples):</b>", styles['Normal']))
                body_flow.append(_list(changes['added'][:6], '+'))
            if changes.get('removed'):
                body_flow.append(Spacer(1, 0.04 * inch))
                body_flow.append(Paragraph("<b>Removed lines (examples):</b>", styles['Normal']))
                body_flow.append(_list(changes['removed'][:6], '-'))
            if changes.get('changed'):
                body_flow.append(Spacer(1, 0.04 * inch))
                body_flow.append(Paragraph("<b>Modified pairs (examples):</b>", styles['Normal']))
                paired = []
                for ch in changes['changed'][:4]:
                    old = ch.get('old', '')
                    new = ch.get('new', '')
                    paired.append(Paragraph(f"<b>Old:</b> {old}<br/><b>New:</b> {new}", styles['Normal']))
                body_flow.append(ListFlowable([ListItem(p) for p in paired], bulletType='bullet', leftIndent=14))

        # For added/removed, show a short snippet preview and counts if content is available
        if status in ('added','removed') and isinstance(section_data.get('content'), str):
            text = section_data.get('content') or ''
            lines = [ln for ln in (text.split('\n') if text else []) if ln.strip()]
            if lines:
                preview = lines[:5]
                body_flow.append(Spacer(1, 0.04 * inch))
                body_flow.append(Paragraph(f"<b>Preview ({len(lines)} lines total):</b>", styles['Normal']))
                body_flow.append(_list(preview, '•'))

        # Build small header table only (splittable content follows outside)
        header_tbl = Table([header], colWidths=[0.80 * 6.0 * inch, 0.20 * 6.0 * inch])
        header_tbl.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BACKGROUND', (0,0), (-1,-1), HexColor('#fafafa')),
            ('BOX', (0,0), (-1,-1), 0.5, HexColor('#e5e7eb')),
            ('INNERPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(header_tbl)
        # Pages line
        pages = section_data.get('pages') if isinstance(section_data, dict) else None
        if isinstance(pages, dict):
            old_p = pages.get('old')
            new_p = pages.get('new')
            elements.append(Paragraph(
                f"<font color='#6b7280'>Pages: {('old p'+str(old_p)) if old_p else 'old —'} → {('new p'+str(new_p)) if new_p else 'new —'}</font>",
                styles['Normal']
            ))
        elements.append(Spacer(1, 0.06 * inch))
        # Body flowables directly (allow page splitting)
        elements.extend(body_flow)

        # If tables section with numeric diffs, append old/new table snapshots
        changes = section_data.get('changes', {}) if status == 'modified' else {}
        num = changes.get('numeric', {}) if isinstance(changes, dict) else {}
        has_num = any(num.get(k) for k in ('changed','added','removed'))
        if has_num and self._is_tables_section(section_name):
            old_txt = section_data.get('old_content') or ''
            new_txt = section_data.get('new_content') or ''
            old_tables = self._extract_table_blocks(old_txt)
            new_tables = self._extract_table_blocks(new_txt)
            if old_tables:
                elements.append(Spacer(1, 0.06 * inch))
                elements.append(Paragraph('<b>Old Table Snapshot</b>', styles['Normal']))
                elements.append(Preformatted('\n'.join(old_tables), styles['Mono']))
            if new_tables:
                elements.append(Spacer(1, 0.06 * inch))
                elements.append(Paragraph('<b>New Table Snapshot</b>', styles['Normal']))
                elements.append(Preformatted('\n'.join(new_tables), styles['Mono']))
        elements.append(Spacer(1, 0.14 * inch))
        return elements

    def _is_tables_section(self, section_name: str) -> bool:
        # Consider Section 9.* or labels containing 'Summary Cost Projection'
        name = section_name or ''
        if re.match(r'^9(\.|\s)', name):
            return True
        return 'summary cost projection' in name.lower()

    def _extract_table_blocks(self, text: str) -> List[str]:
        """Extract contiguous blocks representing the summary tables.
        Start at a header like 'Table Number' or a line starting with 'Table 1', end at blank/heading.
        """
        if not text:
            return []
        lines = text.split('\n')
        blocks: List[str] = []
        buf: List[str] = []
        capturing = False
        for ln in lines:
            s = (ln or '').rstrip()
            if not capturing:
                if re.match(r'^Table\s+Number\b', s, re.IGNORECASE) or re.match(r'^Table\s+\d+\b', s, re.IGNORECASE):
                    capturing = True
                    buf = [s]
                continue
            else:
                # stop on empty line or on a new major heading like '9.1' or 'Table Number' again
                if not s.strip() or re.match(r'^(\d+(?:\.\d+)*)\s', s) or re.match(r'^Table\s+Number\b', s, re.IGNORECASE):
                    if buf:
                        blocks.append('\n'.join(buf).strip())
                        buf = []
                    capturing = False
                    # if a new header triggers, restart capture next iteration
                    if re.match(r'^Table\s+Number\b', s, re.IGNORECASE) or re.match(r'^Table\s+\d+\b', s, re.IGNORECASE):
                        capturing = True
                        buf = [s]
                else:
                    buf.append(s)
        if capturing and buf:
            blocks.append('\n'.join(buf).strip())
        return blocks
