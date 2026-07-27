"""Query due ReminderEvents and dispatch reminder notifications.

respecting learner notification preferences and deduplicating by event + lead time.
"""

from datetime import datetime, timedelta

from sqlmodel import select
from app.reminders.dedupe import build_dedup_key
from app.models.reminder_event import ReminderEvent
from app.scheduler.email_delivery import send_email_reminder
from app.prefs.model import NotificationPreference
from app.schemas.notification import Notification, NotificationPayload, NotificationType
from app.scheduler.runner import run_scheduled_jobs
from app.observability.kpis import update_reminder_kpis


def _get_preference(session, recipient_id: str) -> NotificationPreference | None:
    """Return the recipient's NotificationPreference row, or None if unset."""
    return session.exec(
        select(NotificationPreference).where(NotificationPreference.user_id == int(recipient_id))
    ).first()


def _is_allowed(preference: NotificationPreference | None, event_type: NotificationType) -> bool:
    """Return True if this recipient should receive this type of reminder.

    No preference row at all means the learner has never customized
    settings, so we default to allowed (matches the model's own defaults).
    """
    if preference is None:
        return True
    if preference.opted_out:
        return False
    if event_type == NotificationType.SESSION_REMINDER:
        return preference.session_reminders
    if event_type == NotificationType.DEADLINE_REMINDER:
        return preference.deadline_reminders
    if event_type == NotificationType.AT_RISK_NUDGE:
        return preference.nudges
    return True


def get_due_events(session, now: datetime, lead_time: timedelta) -> list[ReminderEvent]:
    """Return events whose due_at falls within lead_time from now.

    Args:
        session: Active DB session.
        now: Current time.
        lead_time: How far ahead of due_at to start reminding (e.g. 24h, 1h).

    Returns:
        Events due within the window [now, now + lead_time].
    """
    window_end = now + lead_time
    statement = select(ReminderEvent).where(ReminderEvent.due_at >= now).where(ReminderEvent.due_at <= window_end)
    return session.exec(statement).all()


def build_reminder_notification(event: ReminderEvent, lead_time_label: str) -> Notification:
    """Build a Notification for one event + lead-time bucket, with a stable dedup_key.

    Args:
        event: The due event.
        lead_time_label: Short label for which reminder this is (e.g. "24h_before").

    Returns:
        A Notification ready to be sent via run_notification.
    """
    return Notification(
        recipient_id=event.recipient_id,
        type=event.type,
        payload=NotificationPayload(
            title=event.title,
            body=f"Reminder: '{event.title}' is due at {event.due_at.isoformat()}.",
        ),
        dedup_key=build_dedup_key(
            event.recipient_id,
            event.id,
            lead_time_label,
        ),
    )


def dispatch_due_reminders(
    session,
    now: datetime,
    lead_time: timedelta,
    lead_time_label: str,
    deliver_fn=None,
) -> list[Notification]:
    """..."""
    events = get_due_events(session, now, lead_time)

    notifications = []
    events_by_dedup_key = {}
    for event in events:
        preference = _get_preference(session, event.recipient_id)
        if not _is_allowed(preference, event.type):
            continue
        notification = build_reminder_notification(event, lead_time_label)
        notifications.append(notification)
        events_by_dedup_key[notification.dedup_key] = event

    results = run_scheduled_jobs(notifications, deliver_fn=deliver_fn)
    update_reminder_kpis(results, events_by_dedup_key)
    return results


def get_deliver_fn(channel: str):
    """Return the deliver_fn for a given delivery channel.

    Args:
        channel: "in_app" (default, no-op — just records the notification)
            or "email" (sends via SMTP, see email_delivery.py).
    """
    if channel == "email":
        return send_email_reminder
    return None
