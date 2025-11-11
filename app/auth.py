"""
Authentication module for CaseTracker Pro
Handles user login and session management
"""
import streamlit as st
import hashlib
from typing import Optional, Dict

# Test credentials: two users with dk_test01.quagsmo.com domain
# User 1: admin@dk_test01.quagsmo.com, Password: Qm8Kp#Yx2Nv!
# User 2: analyst@dk_test01.quagsmo.com, Password: Tj9Lr$Fw5Bz@
CREDENTIALS = {
    "admin@dk_test01.quagsmo.com": {
        "password_hash": "d4e832168d4de1a9186df3c5312ff3a2d21532bacf26c021f80b6f0f01ad0448",  # Qm8Kp#Yx2Nv!
        "name": "Admin User",
        "role": "admin"
    },
    "analyst@dk_test01.quagsmo.com": {
        "password_hash": "7565393140a6080c4eb6a7b29f60ca6119e6d61f89e88a6ea9f65a199b4057fc",  # Tj9Lr$Fw5Bz@
        "name": "Analyst User",
        "role": "analyst"
    }
}


def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_credentials(email: str, password: str) -> bool:
    """
    Verify user credentials
    
    Args:
        email: User email address
        password: Plain text password
        
    Returns:
        True if credentials are valid, False otherwise
    """
    if email not in CREDENTIALS:
        return False
    
    password_hash = hash_password(password)
    return password_hash == CREDENTIALS[email]["password_hash"]


def login(email: str, password: str) -> bool:
    """
    Authenticate user and create session
    
    Args:
        email: User email address
        password: Plain text password
        
    Returns:
        True if login successful, False otherwise
    """
    if verify_credentials(email, password):
        st.session_state.authenticated = True
        st.session_state.user_email = email
        st.session_state.user_name = CREDENTIALS[email]["name"]
        st.session_state.user_role = CREDENTIALS[email]["role"]
        return True
    return False


def logout():
    """Clear user session"""
    st.session_state.authenticated = False
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.user_role = None


def is_authenticated() -> bool:
    """Check if user is authenticated"""
    return st.session_state.get("authenticated", False)


def get_current_user() -> Optional[Dict[str, str]]:
    """Get current user information"""
    if not is_authenticated():
        return None
    
    return {
        "email": st.session_state.get("user_email"),
        "name": st.session_state.get("user_name"),
        "role": st.session_state.get("user_role")
    }


def require_authentication():
    """
    Decorator/function to require authentication for a page
    Redirects to login if not authenticated
    """
    if not is_authenticated():
        st.warning("⚠️ Please login to access this page")
        st.stop()


def show_login_page():
    """Display the login page UI"""
    st.set_page_config(
        page_title="Login - CaseTracker Pro",
        page_icon="🔐",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    
    # Custom CSS for login page
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
        }
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .login-title {
            color: #3b82f6;
            font-size: 2rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .login-subtitle {
            color: #6b7280;
            font-size: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="login-container">
        <div class="login-header">
            <div class="login-title">🔐 CaseTracker Pro</div>
            <div class="login-subtitle">Please login to continue</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Login form
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="user@dk_test01.quagsmo.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", use_container_width=True, type="primary")
        
        if submit:
            if not email or not password:
                st.error("❌ Please enter both email and password")
            elif login(email, password):
                st.success("✅ Login successful! Redirecting...")
                st.rerun()
            else:
                st.error("❌ Invalid email or password")
