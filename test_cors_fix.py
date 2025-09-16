#!/usr/bin/env python3
"""
Test script to verify CORS fix for PDF viewing.
Run this after deploying the backend to test if PDFs load properly.
"""

import requests
import json

def test_pdf_proxy(backend_url: str, test_pdf_url: str):
    """Test if the PDF proxy endpoint works correctly."""
    try:
        # Test the proxy endpoint
        proxy_url = f"{backend_url}/proxy/pdf?url={test_pdf_url}"
        print(f"Testing: {proxy_url}")
        
        response = requests.get(proxy_url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"CORS Headers:")
        print(f"  Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin')}")
        print(f"  X-Frame-Options: {response.headers.get('X-Frame-Options')}")
        print(f"  Content-Security-Policy: {response.headers.get('Content-Security-Policy')}")
        print(f"  Cross-Origin-Resource-Policy: {response.headers.get('Cross-Origin-Resource-Policy')}")
        
        if response.status_code == 200:
            print("✅ PDF proxy working correctly!")
            return True
        else:
            print(f"❌ PDF proxy failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing PDF proxy: {e}")
        return False

def test_cors_headers(backend_url: str):
    """Test CORS headers on a simple endpoint."""
    try:
        response = requests.get(f"{backend_url}/health", timeout=5)
        print(f"Health endpoint CORS headers:")
        print(f"  Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin')}")
        print(f"  Access-Control-Allow-Methods: {response.headers.get('Access-Control-Allow-Methods')}")
        print(f"  Access-Control-Allow-Headers: {response.headers.get('Access-Control-Allow-Headers')}")
        print(f"  Access-Control-Expose-Headers: {response.headers.get('Access-Control-Expose-Headers')}")
        return True
    except Exception as e:
        print(f"❌ Error testing CORS headers: {e}")
        return False

if __name__ == "__main__":
    # Update these URLs for your deployment
    BACKEND_URL = "https://your-backend.onrender.com"  # Replace with your actual backend URL
    TEST_PDF_URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"  # Test PDF
    
    print("Testing CORS fix for PDF viewing...")
    print("=" * 50)
    
    # Test CORS headers
    print("1. Testing CORS headers...")
    test_cors_headers(BACKEND_URL)
    print()
    
    # Test PDF proxy
    print("2. Testing PDF proxy...")
    test_pdf_proxy(BACKEND_URL, TEST_PDF_URL)
    print()
    
    print("If both tests pass, PDFs should now work in Chrome and Edge!")
    print("Deploy the updated backend and test in your browser.")
