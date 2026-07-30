"""Prometheus KPI definitions and update logic for Ops Console support metrics.

Defines Counter/Gauge/Histogram metrics for support volume, escalation rate,
and resolution time (estimate), and provides a function to refresh them
from the read-only Session/EscalationTicket stores.
"""

from datetime import datetime
from prometheus_client import REGISTRY, Counter, Gauge, Histogram

# --- Safe Metric Retrieval / Initialization ---

if "ops_support_sessions_total" in REGISTRY._names_to_collectors:
    support_sessions_total = REGISTRY._names_to_collectors["ops_support_sessions_total"]
else:
    support_sessions_total = Counter(
        "ops_support_sessions_total",
        "Total number of support sessions observed",
    )

if "ops_escalation_rate" in REGISTRY._names_to_collectors:
    escalation_rate = REGISTRY._names_to_collectors["ops_escalation_rate"]
else:
    escalation_rate = Gauge(
        "ops_escalation_rate",
        "Fraction of sessions that resulted in an escalation ticket, for the last computed window",
    )

if "ops_resolution_time_seconds" in REGISTRY._names_to_collectors:
    resolution_time_seconds = REGISTRY._names_to_collectors["ops_resolution_time_seconds"]
else:
    resolution_time_seconds = Histogram(
        "ops_resolution_time_seconds",
        "Estimated resolution time per escalation ticket (approximation, see metrics.py docstring)",
        buckets=[60, 300, 900, 1800, 3600, 7200, 21600, 86400],
    )

# NOTE: _last_known_total resets to 0 on process restart, which will
# cause one artificially large Counter increment on the first update
# after a restart (catching up to the real total). This is a known
# memory (e.g. in the database). Deferred for this slice; see PR description.
_last_known_total = 0


def update_support_metrics(metrics: dict) -> None:
    """Refresh Prometheus KPIs from an already-computed support metrics dict.

    Increments support_sessions_total by only the delta since the last
    update (Counters can only increase), sets escalation_rate directly,
    and records each ticket's resolution-time estimate as a Histogram
    observation.
    """
    global _last_known_total

    current_total = sum(row["count"] for row in metrics["support_volume"])
    delta = current_total - _last_known_total
    if delta > 0:
        support_sessions_total.inc(delta)
    _last_known_total = current_total

    escalation_rate.set(metrics["escalation_rate"])

    for ticket in metrics["resolution_time"]:
        val = ticket["estimated_resolution_seconds"]
        # If the metric has explicit label names defined elsewhere, fallback safely
        if getattr(resolution_time_seconds, "_labelnames", None):
            resolution_time_seconds.labels(*[""] * len(resolution_time_seconds._labelnames)).observe(val)
        else:
            resolution_time_seconds.observe(val)


# --- Open Issues & At-Risk Metrics (M09) ---

if "ops_open_issues_total" in REGISTRY._names_to_collectors:
    open_issues_total = REGISTRY._names_to_collectors["ops_open_issues_total"]
else:
    open_issues_total = Gauge(
        "ops_open_issues_total",
        "Count of currently open support issues (internal tickets + connector)",
    )

# At-risk counts are published by the escalation lane at ticket-creation time
# through ops_at_risk_issues_count in app/metrics/kpis.py, which already carries
# a cohort label and is the series the Grafana dashboard reads. The dashboard
# endpoint deliberately does not publish a second at-risk gauge: two series for
# one quantity would drift apart and double-count once M05 lands.

ALERT_TYPES = ("high_escalation_rate", "slow_resolution", "open_issues_backlog")

if "ops_active_alerts" in REGISTRY._names_to_collectors:
    active_alerts = REGISTRY._names_to_collectors["ops_active_alerts"]
else:
    active_alerts = Gauge(
        "ops_active_alerts",
        "Whether each dashboard alert is currently firing (1) or clear (0)",
        ["alert_type"],
    )


def update_open_issues_metrics(open_issues: dict) -> None:
    """Refresh the open-issues gauge from an already-computed open-issues dict."""
    open_issues_total.set(open_issues["total_open"])


def update_alert_metrics(alerts: list[dict]) -> None:
    """Publish one 1/0 series per alert type so Grafana can alert on them.

    Every known type is written on every call, including the clear ones.
    Without that, a gauge would keep its last firing value forever once an
    alert stopped, and the dashboard would show a problem that had resolved.
    """
    firing = {alert["type"] for alert in alerts}
    for alert_type in ALERT_TYPES:
        active_alerts.labels(alert_type=alert_type).set(1 if alert_type in firing else 0)


# --- Reminder Metrics ---

if "ops_reminders_sent_total" in REGISTRY._names_to_collectors:
    reminders_sent_total = REGISTRY._names_to_collectors["ops_reminders_sent_total"]
else:
    reminders_sent_total = Counter(
        "ops_reminders_sent_total",
        "Total number of reminder notifications sent",
    )

if "ops_reminders_late_total" in REGISTRY._names_to_collectors:
    reminders_late_total = REGISTRY._names_to_collectors["ops_reminders_late_total"]
else:
    reminders_late_total = Counter(
        "ops_reminders_late_total",
        "Total number of reminders sent at or after their event's due_at",
    )

if "ops_reminder_on_time_rate" in REGISTRY._names_to_collectors:
    reminder_on_time_rate = REGISTRY._names_to_collectors["ops_reminder_on_time_rate"]
else:
    reminder_on_time_rate = Gauge(
        "ops_reminder_on_time_rate",
        "Fraction of sent reminders delivered before their event's due_at, for the last computed batch",
    )


def _as_naive_utc(dt: datetime) -> datetime:
    """Strip tzinfo for safe comparison against naive DB timestamps."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def update_reminder_kpis(notifications: list, events_by_dedup_key: dict) -> None:
    """Refresh Prometheus KPIs from a batch of dispatched reminder notifications.

    Args:
        notifications: Notification results from dispatch_due_reminders
            (only SENT ones count toward on-time tracking).
        events_by_dedup_key: Maps each notification's dedup_key to its
            source ReminderEvent, so we know each one's due_at to compare against.
    """
    from app.schemas.notification import NotificationStatus

    sent = [n for n in notifications if n.status == NotificationStatus.SENT]
    if not sent:
        return

    late_count = 0
    for notification in sent:
        event = events_by_dedup_key.get(notification.dedup_key)
        if event is None:
            continue
        delivery_time = notification.delivered_at or notification.created_at
        if _as_naive_utc(delivery_time) >= _as_naive_utc(event.due_at):
            late_count += 1
    reminders_sent_total.inc(len(sent))
    reminders_late_total.inc(late_count)

    on_time_rate = (len(sent) - late_count) / len(sent)
    reminder_on_time_rate.set(on_time_rate)
