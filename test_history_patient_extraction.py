#!/usr/bin/env python3
"""Test the actual patient extraction function from History page"""

import requests
import urllib.parse
import re

def _extract_patient_from_strings(case_id: str, *, gt_key: str | None = None, ai_label: str | None = None, doc_label: str | None = None) -> str | None:
    try:
        # Only extract from Ground Truth: 3337_LCP_Fatima%20Dodson_Flatworld_Summary_Document.pdf
        if gt_key:
            # Decode URL encoding first
            decoded_key = urllib.parse.unquote(gt_key)
            print(f"Case {case_id}: Decoded key: {decoded_key}")
            
            # Try pattern 1: case_id_LCP_FirstName LastName_rest_of_filename
            m = re.search(rf"{case_id}_LCP_([^_]+(?:_[^_]+)*?)(?:_|\.)", decoded_key)
            if m:
                result = m.group(1).replace("_", " ")
                print(f"Case {case_id}: Pattern 1 match: '{result}'")
                return result
            
            # Try pattern 2: case_id_FirstName LastName_rest_of_filename (without LCP)
            m = re.search(rf"{case_id}_([^_]+(?:\s+[^_]+)*?)(?:_|\.)", decoded_key)
            if m:
                result = m.group(1).strip()
                print(f"Case {case_id}: Pattern 2 match: '{result}'")
                return result
    except Exception as e:
        print(f"Case {case_id}: Error: {e}")
        return None
    return None

def test_actual_api_calls():
    """Test the actual API calls that the History page makes"""
    backend = "http://localhost:8000"
    test_cases = ["4245", "4257", "4279", "4394", "3407"]
    
    print("Testing actual API calls from History page:")
    print("=" * 60)
    
    for case_id in test_cases:
        print(f"\n--- Testing Case {case_id} ---")
        try:
            # This is the same API call made in _case_to_patient_map
            r = requests.get(f"{backend}/s3/{case_id}/latest/assets", timeout=4)
            if r.ok:
                assets = r.json() or {}
                gt_url = assets.get("ground_truth")
                print(f"Ground Truth URL: {gt_url}")
                
                if gt_url:
                    # Extract the S3 key from the URL
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(gt_url)
                    path_parts = parsed.path.split('/')
                    if len(path_parts) >= 3:
                        gt_key = '/'.join(path_parts[3:])  # Skip bucket name
                        print(f"Extracted S3 key: {gt_key}")
                        
                        # Test patient extraction
                        patient_name = _extract_patient_from_strings(case_id, gt_key=gt_key)
                        print(f"Extracted patient name: '{patient_name}'")
                    else:
                        print("Could not extract S3 key from URL")
                else:
                    print("No ground truth URL found")
            else:
                print(f"API call failed: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Exception: {e}")
        print("-" * 40)

if __name__ == "__main__":
    test_actual_api_calls()
