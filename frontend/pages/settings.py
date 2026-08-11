import streamlit as st

from components.styles import page_header
from api.notifications import get_preferences, update_preferences
from api.users import get_teammates, update_password
from api.config import BASE_URL


def show_settings():

    page_header(
        "⚙️",
        "Settings",
        subtitle="Manage your account and notification preferences.",
        eyebrow="Account",
    )

    user = st.session_state.get("user", {}) or {}
    role = st.session_state.get("role", "learner").lower()

    # ============================================================
    # Account
    # ============================================================

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

    # ============================================================
    # Password
    # ============================================================

    st.write("")

    with st.container(border=True):

        st.subheader("🔒 Password")

        st.caption(
            "Create or change your password. "
            "Your current password is never displayed."
        )

        new_password = st.text_input(
            "New password",
            type="password",
            placeholder="Enter your new password",
            key="settings_new_password",
        )

        confirm_password = st.text_input(
            "Confirm password",
            type="password",
            placeholder="Re-enter your new password",
            key="settings_confirm_password",
        )

        st.caption(
            "Password must be at least 8 characters long."
        )

        st.write("")

        if st.button(
            "🔑 Save Password",
            use_container_width=True,
            key="settings_save_password",
        ):

            token = st.session_state.get("token")

            # ----------------------------------------
            # Validate token
            # ----------------------------------------

            if not token:

                st.error(
                    "Your session has expired. Please log in again."
                )

            # ----------------------------------------
            # Validate password
            # ----------------------------------------

            elif not new_password:

                st.error(
                    "Please enter a new password."
                )

            elif len(new_password) < 8:

                st.error(
                    "Password must be at least 8 characters long."
                )

            elif new_password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            # ----------------------------------------
            # Update password
            # ----------------------------------------

            else:

                try:

                    update_password(
                        token,
                        new_password,
                    )

                    # Clear password fields
                    st.session_state.pop(
                        "settings_new_password",
                        None,
                    )

                    st.session_state.pop(
                        "settings_confirm_password",
                        None,
                    )

                    st.success(
                        "Password updated successfully!"
                    )

                except Exception as e:

                    st.error(
                        f"Failed to update password: {e}"
                    )

    # ============================================================
    # Your Group
    # Learner only
    # ============================================================

    if role == "learner":

        st.write("")

        with st.container(border=True):

            st.subheader("👥 Your Group")

            token = st.session_state.get("token")

            try:

                team_info = get_teammates(token)

            except Exception:

                team_info = None

            # ----------------------------------------------------
            # No cohort assigned
            # ----------------------------------------------------

            if (
                not team_info
                or not team_info.get("cohort_id")
            ):

                st.info(
                    "You haven't been assigned to a group yet."
                )

            # ----------------------------------------------------
            # Cohort assigned
            # ----------------------------------------------------

            else:

                st.markdown(
                    f"**Group:** {team_info['cohort_id']}"
                )

                teammates = team_info.get(
                    "teammates",
                    [],
                )

                if not teammates:

                    st.caption(
                        "No other learners in your group yet."
                    )

                else:

                    st.caption(
                        f"{len(teammates)} teammate(s) "
                        "in your group:"
                    )

                    for mate in teammates:

                        display_name = (
                            mate.get("username")
                            or mate.get(
                                "email",
                                "Unknown",
                            )
                        )

                        st.markdown(
                            f"- **{display_name}** "
                            f"&nbsp;·&nbsp; "
                            f"{mate.get('email', '')}"
                        )

    # ============================================================
    # Notification Preferences
    # Learner only
    # ============================================================

    if role == "learner":

        st.write("")

        with st.container(border=True):

            st.subheader("⏰ Reminder Preferences")

            # ----------------------------------------------------
            # Display save result from previous run
            # ----------------------------------------------------

            save_result = st.session_state.pop(
                "settings_prefs_save_result",
                None,
            )

            if save_result:

                kind, message = save_result

                getattr(st, kind)(message)

            token = st.session_state.get("token")

            # ----------------------------------------------------
            # Get preferences
            # ----------------------------------------------------

            try:

                preferences = get_preferences(token)

            except Exception:

                preferences = {
                    "opted_out": False,
                    "session_reminders": True,
                    "deadline_reminders": True,
                    "nudges": True,
                }

            # ----------------------------------------------------
            # Notification checkboxes
            # ----------------------------------------------------

            opted_out = st.checkbox(
                "Opt out of all notifications",
                value=preferences.get(
                    "opted_out",
                    False,
                ),
                key="settings_opted_out",
            )

            session_reminders = st.checkbox(
                "Session reminders",
                value=preferences.get(
                    "session_reminders",
                    True,
                ),
                disabled=opted_out,
                key="settings_session_reminders",
            )

            deadline_reminders = st.checkbox(
                "Deadline reminders",
                value=preferences.get(
                    "deadline_reminders",
                    True,
                ),
                disabled=opted_out,
                key="settings_deadline_reminders",
            )

            nudges = st.checkbox(
                "Learning nudges",
                value=preferences.get(
                    "nudges",
                    True,
                ),
                disabled=opted_out,
                key="settings_nudges",
            )

            st.write("")

            # ----------------------------------------------------
            # Save notification preferences
            # ----------------------------------------------------

            if st.button(
                "💾 Save Preferences",
                use_container_width=True,
                key="settings_save_preferences",
            ):

                payload = {
                    "opted_out": opted_out,
                    "session_reminders": session_reminders,
                    "deadline_reminders": deadline_reminders,
                    "nudges": nudges,
                }

                try:

                    update_preferences(
                        token,
                        payload,
                    )

                    st.session_state[
                        "settings_prefs_save_result"
                    ] = (
                        "success",
                        "Notification preferences updated!",
                    )

                    # Refresh values from backend
                    st.rerun()

                except Exception as e:

                    st.session_state[
                        "settings_prefs_save_result"
                    ] = (
                        "error",
                        f"Failed to update preferences: {e}",
                    )

                    st.rerun()
