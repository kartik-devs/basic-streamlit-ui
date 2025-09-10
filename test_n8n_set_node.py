#!/usr/bin/env python3
"""
Test script to help create a simple n8n workflow with Set node
This script will help you test the webhook data capture
"""

import requests
import json
from datetime import datetime

def test_webhook_data():
    """Test the webhook endpoint with sample data"""
    
    # Sample data that should be sent by n8n Set node
    test_payload = {
        "case_id": "4257",
        "run_id": "4257202509092354",
        "ocr_start_time": "2025-01-09T18:24:30.000Z",
        "ocr_end_time": "2025-01-09T18:24:35.000Z", 
        "total_tokens_used": 1500,
        "total_input_tokens": 800,
        "total_output_tokens": 700,
        "ai_url": "https://s3.amazonaws.com/bucket/4257/ai_report.pdf",
        "doc_url": "https://s3.amazonaws.com/bucket/4257/ai_report.docx",
        "pdf_url": "https://s3.amazonaws.com/bucket/4257/ai_report.pdf"
    }
    
    # Test the webhook endpoint
    webhook_url = "http://localhost:8000/webhook/finalize"
    
    try:
        response = requests.post(webhook_url, json=test_payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Webhook test successful!")
        else:
            print("❌ Webhook test failed!")
            
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")

def create_n8n_set_node_config():
    """Create a sample n8n Set node configuration"""
    
    set_node_config = {
        "name": "Set OCR Data",
        "type": "n8n-nodes-base.set",
        "typeVersion": 1,
        "position": [400, 300],
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": "ocr_start_time",
                        "name": "ocr_start_time",
                        "value": "={{ $json.ocr_start_time || new Date().toISOString() }}",
                        "type": "string"
                    },
                    {
                        "id": "ocr_end_time", 
                        "name": "ocr_end_time",
                        "value": "={{ $json.ocr_end_time || new Date().toISOString() }}",
                        "type": "string"
                    },
                    {
                        "id": "total_tokens_used",
                        "name": "total_tokens_used", 
                        "value": "={{ $json.total_tokens_used || 0 }}",
                        "type": "number"
                    },
                    {
                        "id": "total_input_tokens",
                        "name": "total_input_tokens",
                        "value": "={{ $json.total_input_tokens || 0 }}",
                        "type": "number"
                    },
                    {
                        "id": "total_output_tokens",
                        "name": "total_output_tokens",
                        "value": "={{ $json.total_output_tokens || 0 }}",
                        "type": "number"
                    },
                    {
                        "id": "ai_url",
                        "name": "ai_url",
                        "value": "={{ $json.ai_url || '' }}",
                        "type": "string"
                    },
                    {
                        "id": "doc_url", 
                        "name": "doc_url",
                        "value": "={{ $json.doc_url || '' }}",
                        "type": "string"
                    },
                    {
                        "id": "pdf_url",
                        "name": "pdf_url", 
                        "value": "={{ $json.pdf_url || '' }}",
                        "type": "string"
                    }
                ]
            }
        }
    }
    
    print("🔧 n8n Set Node Configuration:")
    print("=" * 50)
    print(json.dumps(set_node_config, indent=2))
    print("\n📋 Instructions:")
    print("1. Copy the above configuration")
    print("2. In n8n, add a Set node")
    print("3. Paste this configuration into the Set node")
    print("4. Connect it between your data source and webhook")
    print("5. Make sure the webhook URL is: http://your-server:8000/webhook/finalize")

if __name__ == "__main__":
    print("🚀 n8n Set Node Test Script")
    print("=" * 40)
    
    print("\n1. Creating Set Node Configuration...")
    create_n8n_set_node_config()
    
    print("\n2. Testing Webhook Endpoint...")
    test_webhook_data()
    
    print("\n✅ Test complete!")

