#!/usr/bin/env python3

import requests
import json
import base64

def test_code_version_fetch(case_id):
    """Test the exact same logic as in the frontend"""
    try:
        # First try to get stored version from backend
        backend_url = "http://localhost:8000"
        backend_r = requests.get(f"{backend_url}/reports/{case_id}/code-version", timeout=5)
        print(f"Backend response for {case_id}: {backend_r.status_code}")
        if backend_r.ok:
            backend_data = backend_r.json()
            stored_version = backend_data.get("code_version")
            print(f"Stored version from backend: {stored_version}")
            if stored_version and stored_version != "Unknown" and stored_version != "—":
                print(f"Returning stored version: {stored_version}")
                return stored_version
            else:
                print(f"Stored version is empty or dash: '{stored_version}'")
        else:
            print(f"Backend not OK: {backend_r.status_code} - {backend_r.text}")
    except Exception as e:
        print(f"Backend error: {e}")
    
    # Check GitHub API
    print("Checking GitHub API...")
    github_token = "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"
    github_username = "samarth0211"
    repo_name = "n8n-workflows-backup"
    branch = "main"
    file_path = "state/QTgwEEZYYfbRhhPu.version"
    
    github_url = f"https://api.github.com/repos/{github_username}/{repo_name}/contents/{file_path}?ref={branch}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    r = requests.get(github_url, headers=headers, timeout=10)
    print(f"GitHub API response: {r.status_code}")
    if r.ok:
        data = r.json()
        if isinstance(data, dict):
            content = data.get("content")
            encoding = data.get("encoding")
            if content and encoding and encoding.lower() == "base64":
                raw_content = base64.b64decode(content).decode("utf-8", "ignore")
                version_data = json.loads(raw_content)
                version = version_data.get("version", "—")
                github_version = version.replace(".json", "") if isinstance(version, str) else "—"
                print(f"GitHub version: {github_version}")
                return github_version
    else:
        print(f"GitHub API error: {r.text}")
    
    return "—"

if __name__ == "__main__":
    result = test_code_version_fetch("4244")
    print(f"Final result: {result}")
