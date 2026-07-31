import streamlit as st

from components.styles import page_header
from api.dashboard import get_dashboard_metrics


def show_analytics():

    page_header(
        "📈", "Analytics",
        subtitle="Aggregate support metrics across all learners and programs.",
        eyebrow="Insights",
    )

    try:
        with st.spinner("Loading metrics..."):
            metrics = get_dashboard_metrics(st.session_state.token)

        col1, col2, col3 = st.columns(3)

        col1.metric("Support Volume", metrics["support_volume"])
        col2.metric("Escalation Rate", f'{metrics["escalation_rate"]}%')
        col3.metric("Resolution Time", metrics["resolution_time"])

        with st.container(border=True):
            st.subheader("Raw Metrics")
            st.caption("Full payload returned by the analytics service")
            st.json(metrics)

    except Exception as e:
        st.error(f"Couldn't load analytics: {e}")