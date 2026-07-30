import streamlit as st
import pandas as pd
from permissions import can_access

from components.styles import page_header, badge, status_kind
from pages.atrisk import render_atrisk_tab
from api.dashboard import get_dashboard_metrics


def show_dashboard():

    role = st.session_state.get("role")

    if not can_access(role, "Dashboard"):
        st.error("You do not have permission to access this page.")
        return

    page_header(
        "📊", "Dashboard",
        subtitle="A daily snapshot of support volume, escalations, and at-risk learners.",
        eyebrow="Overview",
    )

    metrics = get_dashboard_metrics(st.session_state.token)
    demo_mode = not metrics

    if demo_mode:
        st.warning("Backend unavailable — showing demo data below.", icon="⚠️")

    col1, col2, col3, col4 = st.columns(4)

    if not demo_mode:
        total_sessions = sum(
            item["count"] for item in metrics.get("support_volume", [])
        )
        col1.metric("Sessions", total_sessions)
        col2.metric("Escalation Rate", f'{metrics.get("escalation_rate", 0):.2%}')
        col3.metric("Resolution Records", len(metrics.get("resolution_time", [])))
        col4.metric("Resolution Rate", "N/A")
    else:
        col1.metric("Sessions", 325)
        col2.metric("Escalation Rate", "18%")
        col3.metric("Resolution Records", 16)
        col4.metric("Resolution Rate", "89%")

    st.write("")

    tab_tickets, tab_atrisk = st.tabs(["Tickets", "At-Risk Nudges"])

    # ------------------------------------------------------------------
    # Tickets
    # ------------------------------------------------------------------
    with tab_tickets:

        st.caption("Latest escalations awaiting review")

        tickets = pd.DataFrame(
            {
                "ID": [101, 102, 103],
                "Learner": ["Ahmed", "Sara", "Ali"],
                "Priority": ["High", "Medium", "Low"],
                "Status": ["Open", "Pending", "Closed"],
            }
        )

        for _, row in tickets.iterrows():
            c1, c2, c3 = st.columns([1, 3, 3])
            c1.markdown(f"`#{row['ID']}`")
            c2.write(row["Learner"])
            c3.markdown(
                badge(row["Priority"], status_kind(row["Priority"]))
                + "&nbsp;"
                + badge(row["Status"], status_kind(row["Status"])),
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------
    # At-Risk Nudges
    # ------------------------------------------------------------------
    with tab_atrisk:
        render_atrisk_tab()