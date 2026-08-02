import streamlit as st
import pandas as pd
import requests
import plotly.express as px

from components.styles import badge

from api.config import BASE_URL
BLUE = "#2A63E4"

# (backend field, display label) for the risk-reasons breakdown
REASON_SERIES = [
    ("missed_deadlines_count", "Missed deadlines"),
    ("inactive_count", "Inactivity"),
    ("low_progress_count", "Low progress"),
    ("low_feedback_count", "Low feedback"),
]

# <10% good, 10-25% elevated, >=25% high — tune to your program's tolerance
RISK_BANDS = {"good": 10, "warning": 25}


def _risk_band(pct: float):
    if pct < RISK_BANDS["good"]:
        return "Low risk", "success"
    if pct < RISK_BANDS["warning"]:
        return "Elevated", "warning"
    return "High risk", "danger"


def _get(path: str, token: str, params: dict):
    resp = requests.get(
        f"{BASE_URL}/atrisk{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    resp.raise_for_status()
    return resp.json()


def _chart_layout(fig):
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", color="#16213A"),
    )
    return fig


def render_atrisk_tab():
    """Renders the At-Risk Nudges dashboard content. Call from inside a tab."""

    st.caption("At-risk learners, why they're flagged, and how the count is trending.")

    filt1, filt2, filt3 = st.columns([2, 1.3, 1.3])

    with filt1:
        cohort_id = st.text_input("Cohort", value="cohort_demo", key="atrisk_cohort")
    with filt2:
        run_date = st.date_input("Run date", key="atrisk_run_date")
    with filt3:
        days = st.selectbox(
            "Trend window", [7, 14, 30, 90], index=1,
            format_func=lambda d: f"Last {d} days", key="atrisk_days",
        )

    if not cohort_id.strip():
        st.info("Enter a cohort ID above to load data.")
        return

    token = st.session_state.token
    summary_params = {"cohort_id": cohort_id.strip(), "run_date": str(run_date)}

    try:
        with st.spinner("Loading at-risk summary..."):
            summary = _get("/summary", token, summary_params)
    except requests.RequestException as e:
        st.error(f"Couldn't load the at-risk summary: {e}")
        return

    agg = summary.get("aggregate", {})
    total = agg.get("total_learners", 0)
    at_risk = agg.get("at_risk_count", 0)
    pct = agg.get("at_risk_percent", 0.0)
    band_label, band_kind = _risk_band(pct)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total learners evaluated", total)
    col2.metric("At-risk learners", at_risk)
    col2.markdown(badge(band_label, band_kind), unsafe_allow_html=True)
    col3.metric("At-risk %", f"{pct:.1f}%")
    col3.markdown(badge(band_label, band_kind), unsafe_allow_html=True)

    st.write("")

    chart_col, table_col = st.columns([1.3, 1])

    with chart_col:
        with st.container(border=True):
            st.subheader("Risk reasons breakdown")

            if total:
                reason_df = pd.DataFrame(
                    {
                        "Reason": [label for _, label in REASON_SERIES],
                        "Learners": [agg.get(key, 0) for key, _ in REASON_SERIES],
                    }
                )
                fig = px.bar(reason_df, x="Learners", y="Reason", orientation="h")
                fig.update_traces(marker_color=BLUE)
                fig = _chart_layout(fig)
                fig.update_layout(
                    xaxis=dict(gridcolor="#EEF1F6"), yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No at-risk data for this date yet.")

    with table_col:
        with st.container(border=True):
            st.subheader("At-risk learners")

            try:
                with st.spinner("Loading learners..."):
                    learners_resp = _get("/learners", token, summary_params)
                learner_ids = learners_resp.get("learner_ids", [])
            except requests.RequestException as e:
                st.error(f"Couldn't load learners: {e}")
                learner_ids = []

            if not learner_ids:
                st.info("No at-risk learners for this date.")
            else:
                search = st.text_input("Filter learner ID", key="atrisk_search")
                filtered = (
                    [lid for lid in learner_ids if search.lower() in lid.lower()]
                    if search else learner_ids
                )
                st.caption(f"{len(filtered)} of {len(learner_ids)} learners")
                st.dataframe(
                    pd.DataFrame({"Learner ID": filtered}),
                    use_container_width=True,
                    hide_index=True,
                    height=260,
                )

    st.write("")

    with st.container(border=True):
        st.subheader("At-risk count over time")

        try:
            with st.spinner("Loading trend..."):
                trend_resp = _get(
                    "/trend", token, {"cohort_id": cohort_id.strip(), "days": days}
                )
            trend = trend_resp.get("trend", [])
        except requests.RequestException as e:
            st.error(f"Couldn't load the trend: {e}")
            trend = []

        if trend:
            trend_df = pd.DataFrame(trend)
            fig2 = px.line(trend_df, x="run_date", y="at_risk_count", markers=True)
            fig2.update_traces(line_color=BLUE, marker=dict(color=BLUE, size=7))
            fig2 = _chart_layout(fig2)
            fig2.update_layout(
                yaxis=dict(gridcolor="#EEF1F6"), xaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No trend data for this window yet.")