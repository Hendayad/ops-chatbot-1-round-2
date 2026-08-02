import streamlit as st
from datetime import datetime, timezone, timedelta

from api.reminders import get_reminders
from components.styles import page_header


def show_reminders():
    page_header(
        "⏰",
        "Reminders",
        subtitle="Your reminders.",
    )

    try:
        reminders = get_reminders(st.session_state.token)

        # Remove feedback follow-up reminders completely
        reminders = [
            r for r in reminders
            if str(r["type"]).upper() != "FEEDBACK_FOLLOW_UP"
        ]

    except Exception as e:
        st.error(f"Couldn't load reminders: {e}")
        return

    if not reminders:
        st.info("No reminders.")
        return

    # -----------------------------
    # Filters
    # -----------------------------

    col1, col2 = st.columns(2)

    reminder_types = sorted(
        {r["type"] for r in reminders}
    )

    with col1:
        selected_type = st.selectbox(
            "Reminder Type",
            ["All"] + reminder_types,
        )

    with col2:
        due_filter = st.selectbox(
            "Due Date",
            [
                "All",
                "Overdue",
                "Today",
                "Tomorrow",
                "This Week",
                "Future",
            ],
        )

    now = datetime.now(timezone.utc).date()

    filtered = reminders

    # -----------------------------
    # Filter by type
    # -----------------------------

    if selected_type != "All":
        filtered = [
            r for r in filtered
            if r["type"] == selected_type
        ]

    # -----------------------------
    # Filter by due date
    # -----------------------------

    result = []

    for reminder in filtered:

        due = datetime.fromisoformat(
            reminder["due_at"].replace("Z", "+00:00")
        ).date()

        if due_filter == "All":
            result.append(reminder)

        elif due_filter == "Overdue" and due < now:
            result.append(reminder)

        elif due_filter == "Today" and due == now:
            result.append(reminder)

        elif due_filter == "Tomorrow" and due == now + timedelta(days=1):
            result.append(reminder)

        elif due_filter == "This Week" and now <= due <= now + timedelta(days=7):
            result.append(reminder)

        elif due_filter == "Future" and due > now + timedelta(days=7):
            result.append(reminder)

    # -----------------------------
    # Display reminders
    # -----------------------------

    if not result:
        st.info("No reminders match the selected filters.")
        return

    for reminder in result:
        with st.container(border=True):
            st.subheader(reminder["title"])

            c1, c2 = st.columns(2)

            with c1:
                st.write(f"**Type:** {reminder['type']}")

            with c2:
                st.write(f"**Due:** {reminder['due_at']}")

            if reminder.get("description"):
                st.write(reminder["description"])