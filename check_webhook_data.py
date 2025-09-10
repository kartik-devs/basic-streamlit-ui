#!/usr/bin/env python3
"""
Script to check webhook data in the database
"""

import sqlite3
import json
from datetime import datetime

def check_runs_data():
    """Check the runs table for webhook data"""
    
    try:
        conn = sqlite3.connect("reports.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all runs data
        cursor.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 10")
        runs = cursor.fetchall()
        
        print("📊 Recent Runs Data:")
        print("=" * 80)
        
        if not runs:
            print("No runs data found in database")
            return
        
        for run in runs:
            print(f"ID: {run['id']}")
            print(f"Case ID: {run['case_id']}")
            print(f"Created: {run['created_at']}")
            print(f"OCR Start: {run['ocr_start_time']}")
            print(f"OCR End: {run['ocr_end_time']}")
            print(f"Total Tokens: {run['total_tokens_used']}")
            print(f"Input Tokens: {run['total_input_tokens']}")
            print(f"Output Tokens: {run['total_output_tokens']}")
            print(f"AI URL: {run['ai_url']}")
            print(f"DOC URL: {run['doc_url']}")
            print(f"PDF URL: {run['pdf_url']}")
            print("-" * 40)
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking runs data: {e}")

def test_webhook_with_sample_data():
    """Test webhook with sample data"""
    
    import requests
    
    sample_data = {
        "case_id": "4257",
        "run_id": "4257202509092354",
        "ocr_start_time": "2025-01-09T18:24:30.000Z",
        "ocr_end_time": "2025-01-09T18:24:35.000Z",
        "total_tokens_used": 1500,
        "total_input_tokens": 800,
        "total_output_tokens": 700,
        "ai": {
            "signed_url": "https://s3.amazonaws.com/bucket/4257/ai_report.pdf",
            "key": "4257/Output/ai_report.pdf"
        },
        "docx": {runnign
            "signed_url": "https://s3.amazonaws.com/bucket/4257/ai_report.docx", 
            "key": "4257/Output/ai_report.docx"
        },
        "pdf": {
            "signed_url": "https://s3.amazonaws.com/bucket/4257/ai_report.pdf",
            "key": "4257/Output/ai_report.pdf"
        }
    }
    
    try:
        response = requests.post("http://localhost:8000/webhook/finalize", json=sample_data)
        print(f"Webhook Response: {response.status_code} - {response.json()}")
        
        if response.status_code == 200:
            print("✅ Sample data sent successfully!")
            # Check the data was stored
            check_runs_data()
        else:
            print("❌ Failed to send sample data")
            
    except Exception as e:
        print(f"❌ Error sending sample data: {e}")

if __name__ == "__main__":
    print("🔍 Webhook Data Checker")
    print("=" * 30)
    
    print("\n1. Checking existing runs data...")
    check_runs_data()
    
    print("\n2. Testing with sample data...")
    test_webhook_with_sample_data()

