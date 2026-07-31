import streamlit as st

from components.styles import page_header


def show_guide():

    page_header(
        "📘", "Guide",
        subtitle="What each page is for, and how the pieces fit together.",
        eyebrow="Admin",
    )

    sections = [
        ("📊 Dashboard", "Tickets and At-Risk Nudges", (
            "The **Tickets** tab lists escalations awaiting review. The "
            "**At-Risk Nudges** tab shows learners flagged by the risk model, "
            "why they were flagged, and the trend over time."
        )),
        ("🎫 Escalations", "Full ticket detail", (
            "The complete list of escalated conversations, with the "
            "learner's problem, context, and the assistant's suggested next "
            "step for each one."
        )),
        ("📈 Analytics", "Support metrics", (
            "Aggregate support volume, escalation rate, and resolution time "
            "across all learners and programs."
        )),
        ("👥 Users", "Manage accounts", (
            "Change a user's role, group, and project assignment. Changes "
            "only take effect once you press Update on that row."
        )),
    ]

    for title, subtitle, body in sections:
        with st.container(border=True):
            st.subheader(title)
            st.caption(subtitle)
            st.write(body)

    st.write("")

    with st.container(border=True):
        st.subheader("🔔 Notifications vs. Reminders")
        st.write(
            "The bell icon in the sidebar shows a live count of **open "
            "tickets** — it's a notification, not a setting. **Reminders** "
            "is a separate page that controls a user's own reminder "
            "*preferences* (session reminders, deadline reminders, nudges) "
            "— it doesn't show live alerts."
        )