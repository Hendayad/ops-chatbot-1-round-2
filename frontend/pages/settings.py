import streamlit as st

from components.styles import page_header
from api.notifications import get_preferences, update_preferences


def show_settings():

    page_header(
        "⚙️",
        "Settings",
        subtitle="Manage your account and notification preferences.",
        eyebrow="Account",
    )

    user = st.session_state.get("user", {}) or {}
    role = st.session_state.get("role", "learner").lower()

    # -------------------------
    # Account
    # -------------------------

    st.subheader("👤 Account")

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):

            st.markdown("**Username**")
            st.text_input(
                "Username",
                value=user.get("username", ""),
                disabled=True,
                key="settings_username",
                label_visibility="collapsed",
            )

            st.markdown("**Email**")
            st.text_input(
                "Email",
                value=user.get("email", ""),
                disabled=True,
                key="settings_email",
                label_visibility="collapsed",
            )

    with col2:
        with st.container(border=True):

            st.markdown("**Role**")
            st.text_input(
                "Role",
                value=role.capitalize(),
                disabled=True,
                key="settings_role",
                label_visibility="collapsed",
            )

            st.markdown("**User ID**")
            st.text_input(
                "User ID",
                value=str(user.get("id", "")),
                disabled=True,
                key="settings_user_id",
                label_visibility="collapsed",
            )

    # -------------------------
    # Notification Preferences
    # Learner only
    # -------------------------

    if role == "learner":

        st.write("")

        with st.container(border=True):

            st.subheader("⏰ Reminder Preferences")

            # Show a save result from the *previous* run, if any. This has
            # to happen before st.rerun() is called below, not after — a
            # message shown right before st.rerun() gets wiped by the
            # rerun almost immediately, so it's stashed in session_state
            # and displayed here on the run after the save instead.
            save_result = st.session_state.pop("settings_prefs_save_result", None)
            if save_result:
                kind, message = save_result
                getattr(st, kind)(message)

            token = st.session_state.get("token")

            try:
                preferences = get_preferences(token)
            except Exception:
                preferences = {
                    "opted_out": False,
                    "session_reminders": True,
                    "deadline_reminders": True,
                    "nudges": True,
                }

            # Explicit keys on every checkbox below — without one, Streamlit
            # derives a widget's identity from its label *and* its other
            # arguments, including `disabled`. Since the three reminder
            # checkboxes all had `disabled=opted_out`, toggling opted_out
            # changed their derived identity too, so Streamlit treated them
            # as new widgets and reset them to `value=preferences.get(...)`
            # — silently discarding whatever the user had just checked or
            # unchecked. A stable key removes that dependency entirely.

            opted_out = st.checkbox(
                "Opt out of all notifications",
                value=preferences.get("opted_out", False),
                key="settings_opted_out",
            )

            session_reminders = st.checkbox(
                "Session reminders",
                value=preferences.get("session_reminders", True),
                disabled=opted_out,
                key="settings_session_reminders",
            )

            deadline_reminders = st.checkbox(
                "Deadline reminders",
                value=preferences.get("deadline_reminders", True),
                disabled=opted_out,
                key="settings_deadline_reminders",
            )

            nudges = st.checkbox(
                "Learning nudges",
                value=preferences.get("nudges", True),
                disabled=opted_out,
                key="settings_nudges",
            )


            st.write("")

            if st.button(
                "💾 Save Preferences",
                use_container_width=True,
            ):

                payload = {
                    "opted_out": opted_out,
                    "session_reminders": session_reminders,
                    "deadline_reminders": deadline_reminders,
                    "nudges": nudges,
                }

                try:
                    update_preferences(token, payload)

                    st.session_state["settings_prefs_save_result"] = (
                        "success",
                        "Notification preferences updated!",
                    )

                    # Refresh values from backend
                    st.rerun()

                except Exception as e:
                    st.session_state["settings_prefs_save_result"] = (
                        "error",
                        f"Failed to update preferences: {e}",
                    )
                    st.rerun()