#!/usr/bin/env python3
"""Test S3 key extraction logic"""

import urllib.parse

def test_s3_key_extraction():
    """Test the current S3 key extraction logic"""
    
    # Test URL from the API response
    test_url = "https://finallcpreports.s3.amazonaws.com/4245/Ground%20Truth/4245_LCP_Tyronne%20Craig_final%20draft_6-5-2025.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA47CRYD..."
    
    print(f"Test URL: {test_url}")
    print("=" * 80)
    
    # Current logic
    parsed = urllib.parse.urlparse(test_url)
    print(f"Parsed URL:")
    print(f"  scheme: {parsed.scheme}")
    print(f"  netloc: {parsed.netloc}")
    print(f"  path: {parsed.path}")
    print(f"  query: {parsed.query}")
    
    gt_key = parsed.path.lstrip('/')
    print(f"\nAfter lstrip('/'): {gt_key}")
    
    bucket_name = parsed.netloc.split('.')[0]
    print(f"Bucket name: {bucket_name}")
    
    if gt_key.startswith(f'{bucket_name}/'):
        gt_key = gt_key[len(bucket_name)+1:]
        print(f"After removing bucket name: {gt_key}")
    
    print(f"\nFinal S3 key: {gt_key}")
    
    # Correct logic
    print("\n" + "=" * 80)
    print("Correct S3 key extraction:")
    
    # The correct way to extract S3 key
    path_parts = parsed.path.split('/')
    print(f"Path parts: {path_parts}")
    
    if len(path_parts) >= 3:
        # Skip bucket name (first part after splitting)
        correct_gt_key = '/'.join(path_parts[1:])
        print(f"Correct S3 key: {correct_gt_key}")
        
        # Decode URL encoding
        decoded_key = urllib.parse.unquote(correct_gt_key)
        print(f"Decoded S3 key: {decoded_key}")
    else:
        print("Could not extract S3 key")

if __name__ == "__main__":
    test_s3_key_extraction()
