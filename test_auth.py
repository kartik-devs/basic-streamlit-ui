#!/usr/bin/env python3
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from pathlib import Path

def test_auth():
    # Load config
    config_path = Path("config.yaml")
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    print("Config loaded successfully")
    print("Cookie config:", config.get("cookie", "NOT FOUND"))
    
    # Create authenticator
    try:
        authenticator = stauth.Authenticate(
            config["credentials"],
            config["cookie"]["name"],
            config["cookie"]["key"],
            config["cookie"]["expiry_days"],
        )
        print("Authenticator created successfully")
        
        # Test with a known user
        test_username = "Kartik Rana"
        test_password = "test123"  # You'll need to provide the actual password
        
        print(f"Testing with username: {test_username}")
        print("Available users:", list(config["credentials"]["usernames"].keys()))
        
    except Exception as e:
        print(f"Error creating authenticator: {e}")

if __name__ == "__main__":
    test_auth()
