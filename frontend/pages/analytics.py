import pandas as pd
import plotly.express as px
import streamlit as st

from api.dashboard import get_dashboard_metrics
from components.styles import page_header

BLUE = "#2A78D6"


def show_analytics():

    page_header(
        "📈", "Analytics",
        subtitle="Aggregate support metrics across all learners and programs.",
        eyebrow="Insights",
    )

    try:
        with st.spinner("Loading analytics..."):
            metrics = get_dashboard_metrics(st.session_state.token) or {}

        # .get(..., default) throughout — a response missing a field (e.g. no
        # resolution_time yet for a new cohort) used to raise a bare KeyError
        # here and get swallowed by the except block below as a generic
        # "Couldn't load analytics: 'resolution_time'" message.
        support_volume_rows = metrics.get("support_volume", [])
        resolution_rows = metrics.get("resolution_time", [])

        support_volume = sum(row.get("count", 0) for row in support_volume_rows)
        escalation_rate = metrics.get("escalation_rate", 0) * 100

        resolution_times = [
            row.get("estimated_resolution_seconds", 0) for row in resolution_rows
        ]
        avg_resolution = (
            sum(resolution_times) / len(resolution_times) if resolution_times else 0
        )

        # ===============================
        # KPI Cards
        # ===============================
        c1, c2, c3 = st.columns(3)
        c1.metric("📨 Support Volume", support_volume)
        c2.metric("🚨 Escalation Rate", f"{escalation_rate:.1f}%")
        c3.metric("⏱ Avg Resolution", f"{avg_resolution / 60:.1f} min")

        st.write("")

        # ===============================
        # Chart + Table
        # ===============================
        if support_volume_rows:
            df = pd.DataFrame(support_volume_rows)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")

            with st.container(border=True):

                left, right = st.columns([2.2, 1])

                with left:
                    st.subheader("Support Sessions per Day")

                    fig = px.bar(df, x="date", y="count", text="count")
                    fig.update_traces(textposition="outside", marker_color=BLUE)
                    fig.update_layout(
                        height=320,
                        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", size=13),
                        showlegend=False,
                        margin=dict(l=20, r=20, t=10, b=20),
                        xaxis_title="",
                        yaxis_title="Sessions",
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                    )
                    fig.update_xaxes(showgrid=False, tickformat="%b %d")
                    fig.update_yaxes(showgrid=True, gridcolor="#F2F2EF")

                    st.plotly_chart(fig, use_container_width=True)

                with right:
                    st.subheader("Daily Sessions")

                    table = df.copy()
                    table["date"] = table["date"].dt.strftime("%b %d")
                    table.rename(
                        columns={"date": "Date", "count": "Sessions"}, inplace=True
                    )

                    st.dataframe(
                        table,
                        hide_index=True,
                        use_container_width=True,
                        height=320,
                    )
        else:
            st.info("No support activity found.")

    except Exception as e:
        st.error(f"Couldn't load analytics: {e}")