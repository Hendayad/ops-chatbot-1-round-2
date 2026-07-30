import streamlit as st

from api.reminders import get_reminders
from components.styles import page_header


def show_reminders():
    page_header(
        "🔔",
        "Reminders",
        subtitle="Your upcoming reminders.",
    )

    try:
        reminders = get_reminders(st.session_state.token)
    except Exception as e:
        st.error(f"Couldn't load reminders: {e}")
        return

    if not reminders:
        st.info("No upcoming reminders.")
        return

    for reminder in reminders:
        with st.container(border=True):
            st.subheader(reminder["title"])
            st.write(f"**Type:** {reminder['type']}")
            st.write(f"**Due:** {reminder['due_at']}")