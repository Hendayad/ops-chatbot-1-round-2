import streamlit as st

from api.auth import login
from api.users import get_current_user
from api.notifications import (
    get_notifications,
    mark_as_read,
)

from components.sidebar import show_sidebar
from components.styles import load_css

from pages.dashboard import show_dashboard
from pages.cohorts import show_cohorts
from pages.users import show_users
from pages.chat import show_chat
from pages.tickets import show_tickets
from pages.knowledge_base import show_knowledge_base
from pages.reminders import show_reminders
from pages.analytics import show_analytics
from pages.settings import show_settings
from pages.register import show_register
from pages.guide import show_guide

# --------------------------------------------------
# Page Configuration
# --------------------------------------------------

st.set_page_config(
    page_title="AI Operations Support Agent",
    page_icon="🤖",
    layout="wide",
)

# Hide Streamlit's automatic page navigation
st.markdown("""
<style>
[data-testid="stSidebarNav"]{
    display:none;
}

[data-testid="stSidebarNavSeparator"]{
    display:none;
}
</style>
""", unsafe_allow_html=True)

load_css()

# --------------------------------------------------
# Session State
# --------------------------------------------------

if "token" not in st.session_state:
    st.session_state.token = None

if "user" not in st.session_state:
    st.session_state.user = None

if "role" not in st.session_state:
    st.session_state.role = ""

# --------------------------------------------------
# Login / Register
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
                <div style="font-size:26px;font-weight:700;">
                    OpsAgent AI
                </div>
                <div style="color:#5A6B87;font-size:14px;">
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
                        "Login",
                        use_container_width=True,
                    )

                if submitted:

                    if not email or not password:
                        st.warning("Please enter your email and password.")

                    else:

                        try:
                            with st.spinner("Logging in..."):
                                result = login(email, password)

                            st.session_state.token = result.get("access_token")
                            if st.session_state.token:
                                st.session_state.user = get_current_user(
                                    st.session_state.token
                                )

                            st.session_state.role = result.get("role", "")

                            st.success("Login successful!")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Login failed. Incorrect email or password")

            st.write("")

            if st.button(
                "Create new account",
                use_container_width=True,
            ):
                st.session_state.show_register = True
                st.rerun()

# --------------------------------------------------
# Main Application
# --------------------------------------------------

else:

    notifications = get_notifications(st.session_state.token)

    # ---------------------------------------
    # Notification count
    # ---------------------------------------

    if st.session_state.role == "learner":
        unread = sum(
            not n["is_read"]
            for n in notifications
        )
    else:
        unread = len(notifications)

    notification_count = unread
    overdue_ticket_count = unread if st.session_state.role == "admin" else 0

    # ---------------------------------------
    # Notification bell
    # ---------------------------------------

    top_left, top_right = st.columns([12, 1])

    with top_right:

        bell = "🔔"

        if unread:
            bell = f"🔔 {unread}"

        with st.popover(bell):

            st.subheader("Notifications")

            if not notifications:
                st.info("No notifications.")

            else:

                for notification in notifications:

                    st.markdown(f"**{notification['title']}**")
                    st.caption(notification["message"])

                    # Learners can mark notifications as read
                    if (
                        st.session_state.role == "learner"
                        and not notification["is_read"]
                    ):

                        if st.button(
                            "✓ Mark as read",
                            key=f"read_{notification['id']}",
                        ):

                            mark_as_read(
                                st.session_state.token,
                                notification["id"],
                            )

                            st.rerun()

                    st.divider()

    # ---------------------------------------
    # Sidebar
    # ---------------------------------------

    page = show_sidebar(
        role=st.session_state.role,
        notification_count=notification_count,
        overdue_ticket_count=overdue_ticket_count,
    )

    # ---------------------------------------
    # Pages
    # ---------------------------------------

    if page == "Dashboard":
        show_dashboard()

    elif page == "Chat Viewer":
        show_chat()

    elif page == "Escalations":
        show_tickets()

    elif page == "Knowledge Base":
        show_knowledge_base()

    elif page == "Reminders":
        show_reminders()

    elif page == "Analytics":
        show_analytics()

    elif page == "Settings":
        show_settings()

    elif page == "Users":
        show_users()

    elif page == "Guide":
        show_guide()

    elif page == "Cohorts":
        show_cohorts()


    elif page is None:
        pass

    else:
        st.error(f"Unknown page: {page}")