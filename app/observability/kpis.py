"""Prometheus KPIs for the reminder lane (M04).

Support KPIs live in app/metrics/kpis.py. This module used to define its own
copy of ops_resolution_time_seconds with a different label set, which collided
with that one in the shared Prometheus registry; whichever module imported
second silently received the other's collector, so one of the two lanes was
always writing to the wrong series.
"""

from datetime import datetime

from prometheus_client import Counter, Gauge

from app.metrics.kpis import _get_or_create_metric

# --- Reminder Metrics ---

reminders_sent_total = _get_or_create_metric(
    Counter,
    "ops_reminders_sent_total",
    "Total number of reminder notifications sent",
)

reminders_late_total = _get_or_create_metric(
    Counter,
    "ops_reminders_late_total",
    "Total number of reminders sent at or after their event's due_at",
)

reminder_on_time_rate = _get_or_create_metric(
    Gauge,
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