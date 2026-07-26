"""Prometheus KPI definitions and update logic for Ops Console support metrics.

Defines Counter/Gauge/Histogram metrics for support volume, escalation rate,
and resolution time (estimate), and provides a function to refresh them
from the read-only Session/EscalationTicket stores.
"""

from prometheus_client import Counter, Gauge, Histogram
from datetime import datetime


support_sessions_total = Counter(
    "ops_support_sessions_total",
    "Total number of support sessions observed",
)

escalation_rate = Gauge(
    "ops_escalation_rate",
    "Fraction of sessions that resulted in an escalation ticket, for the last computed window",
)

resolution_time_seconds = Histogram(
    "ops_resolution_time_seconds",
    "Estimated resolution time per escalation ticket (approximation, see metrics.py docstring)",
    buckets=[60, 300, 900, 1800, 3600, 7200, 21600, 86400],
)

# NOTE: _last_known_total resets to 0 on process restart, which will
# cause one artificially large Counter increment on the first update
# after a restart (catching up to the real total). This is a known
# limitation — a durable fix would persist this value outside process
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
        resolution_time_seconds.observe(ticket["estimated_resolution_seconds"])



reminders_sent_total = Counter(
    "ops_reminders_sent_total",
    "Total number of reminder notifications sent",
)

reminders_late_total = Counter(
    "ops_reminders_late_total",
    "Total number of reminders sent at or after their event's due_at",
)

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
        if _as_naive_utc(notification.created_at) >= _as_naive_utc(event.due_at):
            late_count += 1
    reminders_sent_total.inc(len(sent))
    reminders_late_total.inc(late_count)

    on_time_rate = (len(sent) - late_count) / len(sent)
    reminder_on_time_rate.set(on_time_rate)

