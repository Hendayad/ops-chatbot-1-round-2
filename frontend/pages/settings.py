import streamlit as st

from components.styles import page_header, role_badge_html
from api.notifications import get_preferences, update_preferences


def show_settings():

    page_header(
        "⚙️",
        "Settings",
        subtitle="Manage your account and notification preferences.",
    )

    # -------------------------
    # Account
    # -------------------------

    st.subheader("👤 Account")

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            user = st.session_state.get("user", {}) or {}

            st.markdown("**Email**")
            st.write(user.get("email", "Authenticated"))

            st.markdown("**Role**")
            st.markdown(
                role_badge_html(st.session_state.get("role", "")),
                unsafe_allow_html=True,
            )

    with col2:
        with st.container(border=True):
            st.markdown("**Backend API**")
            st.caption("Current connection")
            st.code("http://127.0.0.1:8000/api/v1", language="text")

    # ---------------------------------------------------
    # Notification Preferences (Learners only)
    # ---------------------------------------------------

    role = (st.session_state.get("role") or "").lower()

    if role == "learner":

        st.divider()

        st.subheader("🔔 Notification Preferences")
        st.caption("Choose which notifications you would like to receive.")

        try:
            prefs = get_preferences(st.session_state.token)
        except Exception as e:
            st.error(f"Couldn't load your preferences: {e}")
            return

        with st.container(border=True):

            opted_out = st.checkbox(
                "Disable all notifications",
                value=prefs["opted_out"],
            )

            st.divider()

            session = st.checkbox(
                "Session reminders",
                value=prefs["session_reminders"],
                disabled=opted_out,
                help="Receive reminders before upcoming sessions.",
            )

            deadline = st.checkbox(
                "Deadline reminders",
                value=prefs["deadline_reminders"],
                disabled=opted_out,
                help="Receive reminders before assignment deadlines.",
            )

            nudges = st.checkbox(
                "Learning nudges",
                value=prefs["nudges"],
                disabled=opted_out,
                help="Receive motivational learning reminders.",
            )

            if st.button(
                "💾 Save Preferences",
                use_container_width=True,
            ):
                try:
                    update_preferences(
                        st.session_state.token,
                        {
                            "opted_out": opted_out,
                            "session_reminders": session,
                            "deadline_reminders": deadline,
                            "nudges": nudges,
                        },
                    )

                    st.success("Preferences updated successfully.")

                except Exception as e:
                    st.error(f"Couldn't save your preferences: {e}")

    # -------------------------
    # Logout
    # -------------------------

    st.divider()

    if st.button(
        "🚪 Logout",
        use_container_width=True,
    ):
        st.session_state.token = None
        st.session_state.role = None
        st.session_state.user = {}
        st.session_state.pop("messages", None)
        st.session_state.pop("history_loaded", None)
        st.rerun()