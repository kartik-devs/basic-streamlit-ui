#!/usr/bin/env python3
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from pathlib import Path

def debug_auth():
    # Load config
    config_path = Path("config.yaml")
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    print("=== DEBUG AUTHENTICATION ===")
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
        
        # Check if "Kartik Rana" exists in credentials
        if "Kartik Rana" in config["credentials"]["usernames"]:
            print("✓ 'Kartik Rana' found in credentials")
            user_data = config["credentials"]["usernames"]["Kartik Rana"]
            print(f"  Email: {user_data['email']}")
            print(f"  Name: {user_data['name']}")
            print(f"  Password hash: {user_data['password'][:20]}...")
        else:
            print("✗ 'Kartik Rana' NOT found in credentials")
            print("Available usernames:")
            for username in config["credentials"]["usernames"].keys():
                print(f"  - '{username}'")
        
        # Test authentication manually
        print("\n=== TESTING AUTHENTICATION ===")
        try:
            # This simulates what happens when you click login
            result = authenticator.login()
            print(f"Login result: {result}")
        except Exception as e:
            print(f"Login error: {e}")
            
    except Exception as e:
        print(f"Error creating authenticator: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_auth()
