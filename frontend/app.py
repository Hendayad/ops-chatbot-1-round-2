import streamlit as st

from api.auth import login

from components.navbar import render_top_navbar
from components.styles import load_css

from pages.dashboard import show_dashboard
from pages.users import show_users
from pages.chat import show_chat
from pages.tickets import show_tickets
from pages.knowledge_base import show_knowledge_base
from pages.reminders import show_notifications
from pages.analytics import show_analytics
from pages.settings import show_settings
from pages.register import show_register

# --------------------------------------------------
# Page Configuration
# --------------------------------------------------

st.set_page_config(
    page_title="AI Operations Support Agent",
    page_icon="🤖",
    layout="wide",
)

load_css()

# --------------------------------------------------
# Session State
# --------------------------------------------------

if "token" not in st.session_state:
    st.session_state.token = None

if "user" not in st.session_state:
    st.session_state.user = {}

if "role" not in st.session_state:
    st.session_state.role = ""

# --------------------------------------------------
# Login / Register Page
# --------------------------------------------------

if st.session_state.token is None:

    if "show_register" not in st.session_state:
        st.session_state.show_register = False

    spacer_l, center, spacer_r = st.columns([1, 1.3, 1])

    with center:

        st.markdown(
            """
            <div style="text-align:center; margin-top:32px; margin-bottom:8px;">
                <div style="font-size:40px;">🤖</div>
                <div style="font-family:'Space Grotesk',sans-serif; font-size:26px;
                            font-weight:700;">OpsAgent AI</div>
                <div style="color:#5A6B87; font-size:14px;">
                    Operations Support Portal
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.show_register:

            show_register()

            st.divider()

            if st.button("← Back to Login", use_container_width=True):
                st.session_state.show_register = False
                st.rerun()

        else:

            with st.container(border=True):

                st.subheader("Login")

                with st.form("login_form"):

                    email = st.text_input("Email")
                    password = st.text_input("Password", type="password")

                    submitted = st.form_submit_button(
                        "Login", use_container_width=True
                    )

                if submitted:

                    if not email or not password:
                        st.warning("Please enter your email and password.")

                    else:

                        try:
                            with st.spinner("Logging in..."):
                                result = login(email, password)

                            st.session_state.token = result.get("access_token")
                            st.session_state.user = result.get("user", {})
                            st.session_state.role = result.get("role", "")

                            st.success("Login successful!")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Login failed. {e}")

            st.write("")

            if st.button("Create new account", use_container_width=True):
                st.session_state.show_register = True
                st.rerun()

# --------------------------------------------------
# Main Application
# --------------------------------------------------

else:

    page = render_top_navbar()

    if page == "Dashboard":
        show_dashboard()

    elif page == "Chat Viewer":
        show_chat()

    elif page == "Escalations":
        show_tickets()

    elif page == "Knowledge Base":
        show_knowledge_base()

    elif page == "Reminders":
        show_notifications()

    elif page == "Analytics":
        show_analytics()

    elif page == "Settings":
        show_settings()

    elif page == "Users":
        show_users()

    elif page is None:
        pass

    else:
        st.error("Unknown page selected.")