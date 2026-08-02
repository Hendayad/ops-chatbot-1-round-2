from sqlalchemy import func
from sqlmodel import select
from datetime import datetime
from typing import cast
from sqlalchemy.sql.elements import ColumnElement

from app.models.session import Session as ChatSession
from app.models.escalation_ticket import EscalationTicket
from app.risk.signals import AtRiskSignal, compute_signals
from app.schemas.progress import LearnerProgress


def get_support_volume(session, start: datetime, end: datetime) -> list[dict]:
    """Return daily support session counts between start and end (inclusive)."""
    day = func.date(ChatSession.created_at)

    statement = (
        select(day.label("date"), func.count().label("count"))
        .where(ChatSession.created_at >= start)
        .where(ChatSession.created_at <= end)
        .group_by(day)
        .order_by(day)
    )

    results = session.exec(statement).all()
    return [{"date": row.date, "count": row.count} for row in results]


def get_escalated_session_count(session, start: datetime, end: datetime) -> int:
    """Return the number of unique sessions that produced at least one escalation."""

    statement = (
        select(func.count(func.distinct(EscalationTicket.session_id)))
        .where(EscalationTicket.created_at >= start)
        .where(EscalationTicket.created_at <= end)
        .where(EscalationTicket.session_id.is_not(None))
    )

    return session.exec(statement).one()
def get_escalation_rate(session, start: datetime, end: datetime) -> float:
    """Return the percentage of sessions that resulted in an escalation."""

    daily_counts = get_support_volume(session, start, end)
    total_sessions = sum(row["count"] for row in daily_counts)

    if total_sessions == 0:
        return 0.0

    escalated_sessions = get_escalated_session_count(session, start, end)

    return escalated_sessions / total_sessions

def get_resolution_time_estimate(session, start: datetime, end: datetime) -> list[dict]:
    """Estimate resolution time per ticket, as an approximation only.

    ASSUMPTION: EscalationTicket has no resolved_at/updated_at timestamp,
    and no message-level "last activity" timestamp is accessible outside
    LangGraph's internal checkpoint tables (out of platform-boundary scope
    for this task). As an approved fallback , this
    estimates resolution time as: ticket.created_at - session.created_at
    true time-to-resolution. Tickets with no linked session are excluded.
    This is a known limitation, to be revisited once real ticket-resolution
    tracking exists.
    """
    statement = (
        select(
            cast(ColumnElement, EscalationTicket.id).label("ticket_id"),
            cast(ColumnElement, EscalationTicket.created_at).label("ticket_created_at"),
            cast(ColumnElement, ChatSession.created_at).label("session_created_at"),
        )
        .join(
            ChatSession,
            cast(
                ColumnElement,
                EscalationTicket.session_id == ChatSession.id,
            ),
        )
        .where(EscalationTicket.created_at >= start)
        .where(EscalationTicket.created_at <= end)
    )

    results = session.exec(statement).all()

    estimates = []
    for row in results:
        delta_seconds = (row.ticket_created_at - row.session_created_at).total_seconds()
        estimates.append(
            {
                "ticket_id": row.ticket_id,
                "estimated_resolution_seconds": delta_seconds,
            }
        )

    return estimates


def risk_level_for(signal: AtRiskSignal) -> str:
    """Grade one M05 signal by how many indicators it triggered.

    M05 returns a boolean plus the list of indicators, not a severity, so the
    dashboard derives one: more independent warning signs means a learner needs
    attention sooner. The thresholds live here because they are a reporting
    choice, not part of the detector's contract.
    """
    triggered = len(signal.triggered_indicators)
    if triggered >= 3:
        return "high"
    if triggered == 2:
        return "medium"
    return "low"


def get_at_risk_snapshot(progress_list: list[LearnerProgress] | None = None) -> dict:
    """Return at-risk learner counts by risk level, computed through M05.

    Scoring is delegated to app.risk.signals.compute_signals so the dashboard
    and the detector can never disagree about who is at risk.

    NOTE: nothing persists LearnerProgress yet, so the dashboard endpoint
    currently calls this with no progress and gets an empty snapshot. Once a
    progress store exists, the caller passes it in and this function is
    unchanged.
    """
    signals = compute_signals(progress_list or [])
    at_risk = [signal for signal in signals if signal.is_at_risk]

    by_risk_level: dict[str, int] = {}
    by_cohort: dict[str, dict[str, int]] = {}
    for signal in at_risk:
        level = risk_level_for(signal)
        by_risk_level[level] = by_risk_level.get(level, 0) + 1
        cohort_levels = by_cohort.setdefault(signal.cohort_id, {})
        cohort_levels[level] = cohort_levels.get(level, 0) + 1

    return {
        "at_risk_count": len(at_risk),
        "by_risk_level": by_risk_level,
        "by_cohort": by_cohort,
    }


def get_support_metrics(
    session,
    start: datetime,
    end: datetime,
    progress_list: list[LearnerProgress] | None = None,
) -> dict:
    """Return all Ops dashboard metrics for the given window (M09 / F3.3)."""
    return {
        "support_volume": get_support_volume(session, start, end),
        "escalation_rate": get_escalation_rate(session, start, end),
        "resolution_time": get_resolution_time_estimate(session, start, end),
        "at_risk": get_at_risk_snapshot(progress_list),
    }
