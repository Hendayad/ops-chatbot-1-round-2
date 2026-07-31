"""Notifications triggered when an escalation ticket is created.

Links the escalation trigger flow (app/services/escalation.py) to the
existing idempotent notification pipeline (app/scheduler/runner.py).
"""

from sqlmodel import select

from app.models.escalation_ticket import EscalationTicket
from app.models.notification_preference import NotificationPreference
from app.schemas.notification import Notification, NotificationPayload, NotificationType
from app.scheduler.runner import run_notification


def _get_preference(session, recipient_id: str) -> NotificationPreference | None:
    """Return the recipient's NotificationPreference row, or None if unset."""
    return session.exec(
        select(NotificationPreference).where(NotificationPreference.user_id == int(recipient_id))
    ).first()


def notify_learner_of_escalation(session, ticket: EscalationTicket, deliver_fn=None) -> Notification | None:
    """Notify the learner that their issue was escalated, respecting opt-out.

    Returns None if the ticket has no user_id or the learner has opted out.
    """
    user_id = getattr(ticket, "user_id", None)
    if user_id is None:
        return None

    preference = _get_preference(session, user_id)
    if preference is not None and preference.opted_out:
        return None

    notification = Notification(
        recipient_id=user_id,
        type=NotificationType.FEEDBACK_FOLLOWUP,
        payload=NotificationPayload(
            title="Your issue has been escalated",
            body=f"Your question has been passed to our support team. Summary: {ticket.summary}",
        ),
        dedup_key=f"escalation:{ticket.id}:learner_notified",
    )
    return run_notification(notification, deliver_fn=deliver_fn)


def notify_ops_of_escalation(ticket: EscalationTicket, ops_email: str, deliver_fn=None) -> None:
    """Notify Ops staff that a new escalation ticket was created.

    Does not check learner NotificationPreference — Ops must always be
    informed regardless of the learner's own opt-out.
    """
    notification = Notification(
        recipient_id=ops_email,
        type=NotificationType.FEEDBACK_FOLLOWUP,
        payload=NotificationPayload(
            title=f"New escalation: {ticket.reason}",
            body=f"Ticket {ticket.id} — {ticket.summary}",
        ),
        dedup_key=f"escalation:{ticket.id}:ops_notified",
    )
    run_notification(notification, deliver_fn=deliver_fn)
