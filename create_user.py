#!/usr/bin/env python3
"""
Script to generate proper password hashes for streamlit-authenticator
"""
import streamlit_authenticator as stauth
import yaml

def generate_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a password"""
    hashed_password = stauth.Hasher([password]).generate()[0]
    return hashed_password

def main():
    # Test passwords
    passwords = {
        "kartik_rana": "12345678",
        "admin": "admin123",
        "jane_smith": "jane123",
        "john_doe": "john123",
        "testuser": "test123"
    }
    
    print("Generated password hashes:")
    print("=" * 50)
    
    for username, password in passwords.items():
        hashed = generate_password_hash(password)
        print(f"{username}: {password} -> {hashed}")
    
    print("\n" + "=" * 50)
    print("Update your config.yaml with these hashes")

if __name__ == "__main__":
    main()
