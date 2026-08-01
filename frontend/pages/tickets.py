import streamlit as st
import pandas as pd

from components.styles import page_header, badge, status_kind
from api.tickets import get_tickets


def show_tickets():

    page_header(
        "🎫", "Escalation Tickets",
        subtitle="Conversations the assistant flagged for human follow-up.",
        eyebrow="Support",
    )

    try:
        with st.spinner("Loading tickets..."):
            data = get_tickets(st.session_state.token)

        tickets = data["tickets"]

        if not tickets:
            st.success("No escalation tickets right now 🎉")
            return

        df = pd.DataFrame(tickets)

        display = df[["ticket_id", "reason", "status", "summary", "created_at"]]

        with st.container(border=True):
            st.dataframe(display, use_container_width=True, hide_index=True)

        st.write("")

        selected = st.selectbox("View ticket", df["ticket_id"])

        ticket = df[df.ticket_id == selected].iloc[0]

        with st.container(border=True):

            top_col, badge_col = st.columns([3, 2])
            with top_col:
                st.subheader(f"Ticket {ticket['ticket_id']}")
            with badge_col:
                st.markdown(
                    badge(ticket["status"], status_kind(ticket["status"])),
                    unsafe_allow_html=True,
                )

            st.write("**Problem**")
            st.info(ticket["problem"])

            st.write("**Context**")
            st.write(ticket["context"])

            st.write("**Suggested Next Step**")
            st.success(ticket["suggested_next_step"])

            st.write("**Summary**")
            st.write(ticket["summary"])

            st.write("**User Goal**")
            st.write(ticket["user_goal"])

    except Exception as e:
        st.error(f"Couldn't load tickets: {e}")