"""Streamlit page for viewing and resolving escalation tickets."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from api.tickets import get_ticket, get_tickets, resolve_ticket
from components.styles import badge, page_header, status_kind

_STATUS_OPTIONS = {
    "All": None,
    "Open": "open",
    "In progress": "in_progress",
    "Resolved": "resolved",
    "Closed": "closed",
}


def _safe_text(value: object, fallback: str = "Not provided") -> str:
    """Return clean display text for optional ticket fields."""
    if value is None:
        return fallback

    text = str(value).strip()
    return text or fallback


def _show_ticket_details(ticket: dict[str, object], token: str) -> None:
    """Render one ticket and allow Operations users to resolve it."""
    ticket_id = _safe_text(ticket.get("ticket_id"), "Unknown")
    ticket_status = _safe_text(ticket.get("status"), "unknown").lower()

    with st.container(border=True):
        top_col, badge_col = st.columns([3, 2])

        with top_col:
            st.subheader(f"Ticket {ticket_id}")

        with badge_col:
            st.markdown(
                badge(ticket_status, status_kind(ticket_status)),
                unsafe_allow_html=True,
            )

        st.write("**Reason**")
        st.write(_safe_text(ticket.get("reason")))

        st.write("**Problem**")
        st.info(_safe_text(ticket.get("problem")))

        st.write("**What Was Tried**")
        st.write(_safe_text(ticket.get("what_was_tried")))

        st.write("**Context**")
        st.write(_safe_text(ticket.get("context")))

        st.write("**Suggested Next Step**")
        st.success(_safe_text(ticket.get("suggested_next_step")))

        st.write("**Summary**")
        st.write(_safe_text(ticket.get("summary")))

        st.write("**User Goal**")
        st.write(_safe_text(ticket.get("user_goal")))

        details_col, created_col = st.columns(2)

        with details_col:
            st.caption(
                f"Session: {_safe_text(ticket.get('session_id'), 'Unknown')}"
            )

        with created_col:
            st.caption(
                f"Created: {_safe_text(ticket.get('created_at'), 'Unknown')}"
            )

        can_resolve = ticket_status not in {"resolved", "closed"}

        if st.button(
            "Resolve ticket",
            type="primary",
            disabled=not can_resolve,
            use_container_width=True,
            key=f"resolve_{ticket_id}",
        ):
            try:
                with st.spinner("Resolving ticket..."):
                    resolve_ticket(token, ticket_id)

                st.success("Ticket resolved successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Couldn't resolve ticket: {exc}")

        if not can_resolve:
            st.caption("This ticket is already resolved or closed.")


def show_tickets() -> None:
    """Display Operations escalation tickets."""
    page_header(
        "🎫",
        "Escalation Tickets",
        subtitle="Conversations the assistant flagged for human follow-up.",
        eyebrow="Support",
    )

    token = st.session_state.get("token")
    if not token:
        st.error("Your session has expired. Please sign in again.")
        return

    filter_col, refresh_col = st.columns([4, 1])

    with filter_col:
        selected_status_label = st.selectbox(
            "Filter by status",
            options=list(_STATUS_OPTIONS),
            index=0,
        )

    with refresh_col:
        st.write("")
        st.write("")
        if st.button(
            "Refresh",
            use_container_width=True,
            help="Reload tickets from the backend.",
        ):
            st.rerun()

    selected_status = _STATUS_OPTIONS[selected_status_label]

    try:
        with st.spinner("Loading tickets..."):
            data = get_tickets(
                token,
                status=selected_status,
                offset=0,
                limit=100,
            )

        tickets = data.get("tickets", [])

        if not tickets:
            if selected_status:
                st.info(
                    f"No {selected_status_label.lower()} escalation tickets."
                )
            else:
                st.success("No escalation tickets right now 🎉")
            return

        df = pd.DataFrame(tickets)

        display_columns = [
            "ticket_id",
            "reason",
            "status",
            "summary",
            "created_at",
        ]
        for column in display_columns:
            if column not in df.columns:
                df[column] = ""

        display = df[display_columns].copy()

        with st.container(border=True):
            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
            )

        st.write("")

        ticket_ids = [
            str(ticket_id)
            for ticket_id in df["ticket_id"].dropna().tolist()
        ]

        if not ticket_ids:
            st.warning("The backend returned tickets without ticket IDs.")
            return

        selected_ticket_id = st.selectbox(
            "View ticket",
            options=ticket_ids,
        )

        try:
            with st.spinner("Loading ticket details..."):
                detail_response = get_ticket(token, selected_ticket_id)

            ticket = detail_response.get("ticket", detail_response)

            if not isinstance(ticket, dict):
                st.error("The backend returned an invalid ticket response.")
                return

            _show_ticket_details(ticket, token)

        except Exception as exc:
            st.error(f"Couldn't load ticket details: {exc}")

    except Exception as exc:
        st.error(f"Couldn't load tickets: {exc}")