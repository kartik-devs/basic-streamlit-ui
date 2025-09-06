#!/usr/bin/env python3
"""Test the fixed regex pattern"""

import re
import urllib.parse

def test_fixed_regex():
    """Test the fixed regex pattern against actual file names"""
    
    # Test cases from the API responses
    test_cases = [
        {
            "case_id": "4245",
            "gt_key": "4245/Ground%20Truth/4245_LCP_Tyronne%20Craig_final%20draft_6-5-2025.pdf",
            "expected": "Tyronne Craig"
        },
        {
            "case_id": "4257", 
            "gt_key": "4257/Ground%20Truth/4257_LCP_Carlos%20John_final%20draft_6-6-2026.pdf",
            "expected": "Carlos John"
        },
        {
            "case_id": "4279",
            "gt_key": "4279/Ground%20Truth/4279_LCP_Jesse%20Perez.pdf", 
            "expected": "Jesse Perez"
        },
        {
            "case_id": "3407",
            "gt_key": "3407/Ground%20Truth/3407_LCP_Blanca%20Ortiz_Flatworld_Summary_Document.pdf",
            "expected": "Blanca Ortiz"
        }
    ]
    
    def _extract_patient_from_strings_fixed(case_id: str, *, gt_key: str | None = None) -> str | None:
        try:
            if gt_key:
                # Decode URL encoding first
                decoded_key = urllib.parse.unquote(gt_key)
                print(f"Case {case_id}: Decoded key: {decoded_key}")
                
                # Try pattern 1: case_id_LCP_FirstName LastName_rest_of_filename
                # This pattern handles spaces in names properly
                m = re.search(rf"{case_id}_LCP_([^_]+(?:\s+[^_]+)*?)(?:_|\.)", decoded_key)
                if m:
                    result = m.group(1).strip()
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
    
    print("Testing fixed regex patterns:")
    print("=" * 60)
    
    for test_case in test_cases:
        print(f"\n--- Testing Case {test_case['case_id']} ---")
        print(f"Expected: {test_case['expected']}")
        result = _extract_patient_from_strings_fixed(test_case['case_id'], gt_key=test_case['gt_key'])
        print(f"Result: '{result}'")
        print(f"Match: {'✓' if result == test_case['expected'] else '✗'}")
        print("-" * 40)

if __name__ == "__main__":
    test_fixed_regex()
