"""Prometheus KPIs for Ops support observability (M09 / F3.3).

This is the single place where support KPIs are defined. Every metric here is
written to by a real runtime path — the ticket lane, the answering lane, or the
dashboard endpoint — so the /metrics endpoint never exposes a series that stays
permanently empty.

The dashboard at dashboards/grafana.json reads only the metric names defined
below.
"""

from typing import Callable, TypeVar, cast

from prometheus_client import REGISTRY, Counter, Gauge, Histogram
from prometheus_client.registry import Collector

# EscalationTicket carries no cohort column, so ticket-derived series are
# published under this single label value until the column exists. Sharing one
# constant keeps the ticket lane and the dashboard on the same series instead of
# silently splitting one quantity in two.
DEFAULT_COHORT_LABEL = "default"

# --- Safe Registration Helper Utility ---

T = TypeVar("T", bound=Collector)


def _get_or_create_metric(
    metric_cls: Callable[..., T], name: str, documentation: str, labelnames=(), **kwargs
) -> T:
    """Retrieve an existing metric from REGISTRY or create a new one safely."""
    if name in REGISTRY._names_to_collectors:
        return cast(T, REGISTRY._names_to_collectors[name])
    try:
        return metric_cls(name, documentation, labelnames=labelnames, **kwargs)
    except ValueError:
        return cast(T, REGISTRY._names_to_collectors[name])


# --- Support Volume & Resolution ---

SUPPORT_VOLUME = _get_or_create_metric(
    Counter,
    "ops_support_volume_total",
    "Total support tickets received",
    labelnames=["cohort", "severity"],
)

SUPPORT_SESSIONS = _get_or_create_metric(
    Counter,
    "ops_support_sessions_total",
    "Total number of support sessions observed",
)

RESOLUTION_TIME = _get_or_create_metric(
    Histogram,
    "ops_resolution_time_seconds",
    "Time taken to resolve support tickets",
    labelnames=["cohort"],
    buckets=(60, 300, 600, 1800, 3600, 7200, 86400),
)

AT_RISK_ISSUES = _get_or_create_metric(
    Gauge,
    "ops_at_risk_issues_count",
    "Count of currently active or at-risk tickets",
    labelnames=["cohort", "risk_level"],
)

# --- Bot & Escalation Metrics ---

DEFLECTION_RATE = _get_or_create_metric(
    Counter,
    "ops_bot_deflection_total",
    "Total queries resolved automatically without human intervention",
    labelnames=["cohort"],
)

ESCALATIONS_TOTAL = _get_or_create_metric(
    Counter,
    "ops_escalations_total",
    "Total queries escalated to human operators",
    labelnames=["cohort", "reason"],
)

ESCALATION_RATE = _get_or_create_metric(
    Gauge,
    "ops_escalation_rate",
    "Fraction of sessions that resulted in an escalation ticket, for the last computed window",
)

CONNECTOR_SYNC_FAILURES = _get_or_create_metric(
    Counter,
    "ops_connector_sync_failures_total",
    "Total failed ticket synchronization attempts with external connectors",
    labelnames=["connector_name"],
)

FIRST_RESPONSE_TIME = _get_or_create_metric(
    Histogram,
    "ops_first_response_time_seconds",
    "Time taken to provide the initial response to a query",
    labelnames=["cohort"],
    buckets=(1, 2, 5, 10, 30, 60, 300),
)

# --- Open Issues & Alerts ---

OPEN_ISSUES = _get_or_create_metric(
    Gauge,
    "ops_open_issues_total",
    "Count of currently open support issues (internal tickets + connectors)",
)

ALERT_TYPES = ("high_escalation_rate", "slow_resolution", "open_issues_backlog")

ACTIVE_ALERTS = _get_or_create_metric(
    Gauge,
    "ops_active_alerts",
    "Whether each dashboard alert is currently firing (1) or clear (0)",
    labelnames=["alert_type"],
)


# --- Helper Utility Functions ---


def track_ticket_created(cohort: str, severity: str = "normal") -> None:
    """Increment support volume metric upon ticket creation."""
    SUPPORT_VOLUME.labels(cohort=cohort, severity=severity).inc()


def track_resolution_time(cohort: str, duration_seconds: float) -> None:
    """Observe duration taken to resolve a support ticket."""
    RESOLUTION_TIME.labels(cohort=cohort).observe(duration_seconds)


def track_first_response_time(cohort: str, duration_seconds: float) -> None:
    """Observe time taken to send the first response to the learner."""
    FIRST_RESPONSE_TIME.labels(cohort=cohort).observe(duration_seconds)


def update_at_risk_count(cohort: str, risk_level: str, count: int) -> None:
    """Set current count of active at-risk issues for a specific cohort."""
    AT_RISK_ISSUES.labels(cohort=cohort, risk_level=risk_level).set(count)


def track_query_deflected(cohort: str) -> None:
    """Increment deflection counter when bot resolves a query without human intervention."""
    DEFLECTION_RATE.labels(cohort=cohort).inc()


def track_escalation(cohort: str, reason: str = "unknown") -> None:
    """Increment escalation counter when an issue is escalated to human Ops."""
    ESCALATIONS_TOTAL.labels(cohort=cohort, reason=reason).inc()


def track_connector_failure(connector_name: str) -> None:
    """Record a failure during external connector synchronization."""
    CONNECTOR_SYNC_FAILURES.labels(connector_name=connector_name).inc()


# --- Dashboard Refresh Functions ---

# SUPPORT_SESSIONS is a Counter, which may only increase, while the dashboard
# query returns an absolute total for its window. Only the delta since the last
# refresh is added. This resets to 0 on process restart, producing one catch-up
# increment on the first refresh afterwards.
_last_known_total = 0


def update_support_metrics(metrics: dict) -> None:
    """Refresh support KPIs from an already-computed dashboard metrics dict."""
    global _last_known_total

    current_total = sum(row["count"] for row in metrics["support_volume"])
    delta = current_total - _last_known_total
    if delta > 0:
        SUPPORT_SESSIONS.inc(delta)
    _last_known_total = current_total

    ESCALATION_RATE.set(metrics["escalation_rate"])

    for ticket in metrics["resolution_time"]:
        track_resolution_time(DEFAULT_COHORT_LABEL, ticket["estimated_resolution_seconds"])

    update_at_risk_metrics(metrics.get("at_risk", {}))


def update_at_risk_metrics(at_risk: dict) -> None:
    """Publish the at-risk gauge from an M05 snapshot, per cohort and risk level.

    Every cohort/level pair present in the snapshot is written, including the
    zero ones, so a cohort that recovered does not keep its last firing value.
    """
    for cohort, by_level in at_risk.get("by_cohort", {}).items():
        for risk_level, count in by_level.items():
            update_at_risk_count(cohort, risk_level, count)


def update_open_issues_metrics(open_issues: dict) -> None:
    """Refresh the open-issues gauge from an already-computed open-issues dict."""
    OPEN_ISSUES.set(open_issues["total_open"])


def update_alert_metrics(alerts: list[dict]) -> None:
    """Publish one 1/0 series per alert type so Grafana can alert on them.

    Every known type is written on every call, including the clear ones.
    Without that, a gauge would keep its last firing value forever once an
    alert stopped, and the dashboard would show a problem that had resolved.
    """
    firing = {alert["type"] for alert in alerts}
    for alert_type in ALERT_TYPES:
        ACTIVE_ALERTS.labels(alert_type=alert_type).set(1 if alert_type in firing else 0)
