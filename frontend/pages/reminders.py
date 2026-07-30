import streamlit as st

from components.styles import page_header
from api.notifications import (
    get_preferences,
    update_preferences,
)


def show_notifications():

    page_header(
        "🔔", "Notification Preferences",
        subtitle="Choose which updates you'd like to receive.",
        eyebrow="Settings",
    )

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
            help="Reminders about upcoming or missed sessions.",
        )

        deadline = st.checkbox(
            "Deadline reminders",
            value=prefs["deadline_reminders"],
            disabled=opted_out,
            help="Reminders as assignment or course deadlines approach.",
        )

        nudges = st.checkbox(
            "Learning nudges",
            value=prefs["nudges"],
            disabled=opted_out,
            help="Occasional encouragement to keep up your progress.",
        )

        st.write("")

        if st.button("Save Preferences", use_container_width=True):

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
                st.success("Preferences updated.")
            except Exception as e:
                st.error(f"Couldn't save your preferences: {e}")