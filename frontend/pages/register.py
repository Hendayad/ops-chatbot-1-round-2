import streamlit as st
import re

from components.styles import page_header
from api.register import register


def show_register():

    page_header(
        "📝", "Create Account",
        subtitle="Set up access to the Operations Support Portal.",
    )

    with st.form("register_form", border=True):

        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")

        submitted = st.form_submit_button(
            "Register", use_container_width=True
        )

    if submitted:

        if not username or not email or not password:
            st.warning("Please fill in every field.")

        elif "@" not in email:
            st.warning("Enter a valid email address.")

        elif len(password) < 8:
            st.warning("Password must be at least 8 characters.")

        elif not re.search(r"[A-Z]", password):
            st.warning("Password must contain at least one uppercase letter.")

        elif not re.search(r"[a-z]", password):
            st.warning("Password must contain at least one lowercase letter.")

        elif not re.search(r"\d", password):
            st.warning("Password must contain at least one number.")

        elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            st.warning(
                "Password must contain a special character, "
                'such as !, @, #, $, %, or &.'
            )

        elif password != confirm_password:
            st.error("Passwords do not match.")

        else:
            try:
                with st.spinner("Creating account..."):
                    register(email, username, password)
        
                st.success("Account created successfully! Please login.")
        
            except Exception as exc:
                st.error(f"Registration failed: {exc}")