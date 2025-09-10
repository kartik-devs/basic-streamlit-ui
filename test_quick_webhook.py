#!/usr/bin/env python3
"""
Test script to simulate the quick n8n workflow response
"""

import requests
import json
from datetime import datetime

def test_quick_webhook():
    """Test the quick webhook with the exact data structure you showed"""
    
    # This is the exact response structure you showed me
    test_response = [
        {
            "section4 end time": "2025-09-09T21:36:48.296+05:30",
            "section4 start time": "2025-09-09T21:36:48.297+05:30"
        },
        {
            "section9 end time": "2025-09-09T21:58:52.202+05:30",
            "section9 start time": "2025-09-09T21:58:52.203+05:30"
        },
        {
            "status": "success",
            "bucket": "finallcpreports",
            "case_id": "4257",
            "file_id": "202509091628",
            "pdf": {
                "key": "4257/Output/202509091628-4257-highlighted.pdf",
                "s3_path": "s3://finallcpreports/4257/Output/202509091628-4257-highlighted.pdf",
                "bytes": 126183,
                "signed_url": "https://finallcpreports.s3.amazonaws.com/4257/Output/202509091628-4257-highlighted.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA47CRYDBE5XWTMKOR%2F20250909%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250909T164502Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=7b8a038dcba67621655fc362f89e1a476689bacf5cafc41dcc22d6e7b32e02a4"
            },
            "docx": {
                "key": "4257/Output/202509091628-4257-highlighted.docx",
                "s3_path": "s3://finallcpreports/4257/Output/202509091628-4257-highlighted.docx",
                "bytes": 56918,
                "signed_url": "https://finallcpreports.s3.amazonaws.com/4257/Output/202509091628-4257-highlighted.docx?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA47CRYDBE5XWTMKOR%2F20250909%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250909T164502Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=5886e49154eeaf749468665c7f864e03b3def78912fe6413368d75b822310876"
            }
        }
    ]
    
    # Test the webhook endpoint
    webhook_url = "http://localhost:8000/webhook/finalize"
    
    print("🚀 Testing Quick Webhook Response")
    print("=" * 50)
    print(f"📤 Sending data to: {webhook_url}")
    print(f"📊 Data structure: {len(test_response)} items")
    
    try:
        response = requests.post(webhook_url, json=test_response, timeout=10)
        print(f"📥 Response Status: {response.status_code}")
        print(f"📥 Response Body: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Quick webhook test successful!")
            print("\n🔍 Now check your database to see if the data was stored correctly")
        else:
            print("❌ Quick webhook test failed!")
            
    except Exception as e:
        print(f"❌ Error testing quick webhook: {e}")

def show_expected_data_structure():
    """Show what data structure we're working with"""
    
    print("\n📋 Expected Data Structure:")
    print("=" * 50)
    print("The n8n workflow will send an array with:")
    print("1. Section timing data (section4, section9 start/end times)")
    print("2. Main result object with:")
    print("   - status: 'success'")
    print("   - bucket: 'finallcpreports'")
    print("   - case_id: '4257'")
    print("   - file_id: '202509091628'")
    print("   - pdf: {key, s3_path, bytes, signed_url}")
    print("   - docx: {key, s3_path, bytes, signed_url}")
    
    print("\n🎯 What we need to extract for the table:")
    print("- OCR Start: section4 start time")
    print("- OCR End: section9 end time") 
    print("- Total Tokens: (we'll need to calculate or add this)")
    print("- Input Tokens: (we'll need to calculate or add this)")
    print("- Output Tokens: (we'll need to calculate or add this)")

if __name__ == "__main__":
    show_expected_data_structure()
    test_quick_webhook()

