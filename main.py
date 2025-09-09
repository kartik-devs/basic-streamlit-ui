import streamlit as st
import yaml
from pathlib import Path
from typing import Tuple

import streamlit_authenticator as stauth

# Local modules
from app.ui import inject_base_styles, show_header
from app.auth import register_user, load_config, user_exists, is_allowed_email
import re


def load_auth_config() -> Tuple[dict, str, str]:
    config_path = Path("config.yaml")
    if not config_path.exists():
        st.error("Missing config.yaml for authentication.")
        st.stop()

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    cookie_name = "casetracker_auth"
    cookie_key = "casetracker_signature"
    return config, cookie_name, cookie_key


def build_authenticator():
    config, cookie_name, cookie_key = load_auth_config()
    authenticator = stauth.Authenticate(
        config["credentials"],
        cookie_name,
        cookie_key,
        cookie_expiry_days=1,
    )
    return authenticator


def main() -> None:
    st.set_page_config(
        page_title="Login - CaseTracker Pro",
        page_icon="🔐",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    

    inject_base_styles()
    show_header(
        title="Login",
        subtitle=(
            "Enter your credentials to continue. After login you'll be taken "
            "to the Case Report page to submit a Case ID."
        ),
        icon="🔐",
    )

    authenticator = build_authenticator()

    # Login/Register Tabs
    with st.container():
        tabs = st.tabs(["Sign In", "Register"])

        with tabs[0]:
            st.subheader("Sign in")
            authenticator.login(location="main")

        with tabs[1]:
            st.subheader("Create an account")
            with st.form("register_form"):
                col1, col2 = st.columns(2)
                with col1:
                    reg_username = st.text_input("Username")
                    reg_name = st.text_input("Full name")
                with col2:
                    reg_email = st.text_input("Email")
                    reg_password = st.text_input("Password", type="password")
                    reg_password2 = st.text_input("Confirm password", type="password")

                submitted = st.form_submit_button("Register", type="primary")
                if submitted:
                    email_input = (reg_email or "").strip()
                    email_ok = is_allowed_email(email_input)
                    if not reg_username or not reg_name or not reg_email or not reg_password:
                        st.error("Please fill all fields.")
                    elif not email_ok:
                        st.error("Please use a supported email provider (e.g., gmail.com, outlook.com).")
                    elif reg_password != reg_password2:
                        st.error("Passwords do not match.")
                    elif user_exists(load_config(), reg_username):
                        st.error("Username already exists.")
                    else:
                        try:
                            register_user(reg_username, reg_name, email_input, reg_password)
                        except ValueError:
                            st.error("Email domain not allowed or invalid format.")
                        else:
                            st.success("Account created. You can now sign in.")

        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("authentication_status") is True:
        st.success(f"Welcome {st.session_state.get('name', '')}!")

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Go to Case Report", type="primary"):
                # Use st.switch_page which is the proper Streamlit way
                st.switch_page("pages/01_Case_Report.py")
        with c2:
            authenticator.logout("Log out", "main")

    elif st.session_state.get("authentication_status") is False:
        st.error("Invalid username or password.")
    else:
        st.info("Please enter your credentials to continue.")


if __name__ == "__main__":
    main()




      