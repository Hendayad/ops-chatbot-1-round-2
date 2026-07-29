<<<<<<< Updated upstream
"""Prometheus KPIs and observability metrics for Ops Chatbot.
=======
﻿"""Prometheus metrics and KPI tracking for operations and support."""

from prometheus_client import Counter, Gauge, Histogram
>>>>>>> Stashed changes

This module defines and safely registers core Prometheus metrics to avoid
duplicate registration errors during pytest suite execution.
"""

from prometheus_client import REGISTRY, Counter, Gauge, Histogram

# --- Safe Registration Helper Utility ---


def _get_or_create_metric(metric_cls, name: str, documentation: str, labelnames=(), **kwargs):
    """Retrieve an existing metric from REGISTRY or create a new one safely."""
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    try:
        return metric_cls(name, documentation, labelnames=labelnames, **kwargs)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


# --- Existing Metrics ---

SUPPORT_VOLUME = _get_or_create_metric(
    Counter,
    "ops_support_volume_total",
    "Total support tickets received",
<<<<<<< Updated upstream
    labelnames=["cohort", "severity"],
=======
    ["cohort", "severity"],
>>>>>>> Stashed changes
)

RESOLUTION_TIME = _get_or_create_metric(
    Histogram,
    "ops_resolution_time_seconds",
    "Time taken to resolve support tickets",
<<<<<<< Updated upstream
    labelnames=["cohort"],
=======
    ["cohort"],
>>>>>>> Stashed changes
    buckets=(60, 300, 600, 1800, 3600, 7200, 86400),
)

AT_RISK_ISSUES = _get_or_create_metric(
    Gauge,
    "ops_at_risk_issues_count",
    "Count of currently active or at-risk tickets",
<<<<<<< Updated upstream
    labelnames=["cohort", "risk_level"],
)

# --- Additional Bot & Escalation Metrics ---

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


# --- Helper Utility Functions ---


def track_ticket_created(cohort: str, severity: str = "normal") -> None:
    """Increment support volume metric upon ticket creation."""
=======
    ["cohort", "risk_level"],
)


def track_support_ticket(cohort: str, severity: str) -> None:
    """Increment support ticket volume counter."""
>>>>>>> Stashed changes
    SUPPORT_VOLUME.labels(cohort=cohort, severity=severity).inc()


def track_resolution_time(cohort: str, duration_seconds: float) -> None:
<<<<<<< Updated upstream
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
=======
    """Observe resolution time duration for a ticket."""
    RESOLUTION_TIME.labels(cohort=cohort).observe(duration_seconds)


def update_at_risk_count(cohort: str, risk_level: str, count: int) -> None:
    """Set active at-risk tickets count."""
    AT_RISK_ISSUES.labels(cohort=cohort, risk_level=risk_level).set(count)
>>>>>>> Stashed changes
