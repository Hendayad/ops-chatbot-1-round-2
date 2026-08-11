"""
Notifications related to support tickets.

Notification rules:

LEARNER
-------
The learner receives an immediate notification when
their issue is escalated.

ADMIN
-----
The admin receives a notification when a ticket has
remained unresolved for more than 2 days.

PROGRAM_LEAD
------------
The program lead receives a notification when a ticket
has remained unresolved for more than 2 days.

RESOLVED / CLOSED
-----------------
Resolved or closed tickets do not generate staff
notifications.

All notifications use the single category:

    feedback_followup

Reminders are separate and are not modified here.
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.escalation_ticket import EscalationTicket
from app.models.notification_preference import NotificationPreference
from app.models.user import User, UserRole
from app.services.notification_service import (
    create_feedback_followup_notification,
    notification_exists,
)


# ============================================================
# Configuration
# ============================================================

STAFF_TICKET_AGE = timedelta(days=2)


# ============================================================
# Learner notification preferences
# ============================================================

def _get_preference(
    session: Session,
    user_id: int,
) -> NotificationPreference | None:
    """
    Return notification preferences for a user.

    If no preference row exists, notifications are allowed.
    """

    return session.exec(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id
        )
    ).first()


# ============================================================
# Learner notification
# ============================================================

def notify_learner_of_escalation(
    session: Session,
    ticket: EscalationTicket,
) -> None:
    """
    Immediately notify the learner that their issue
    has been escalated.

    The learner's global notification opt-out is respected.
    """

    user_id = getattr(ticket, "user_id", None)

    if user_id is None:
        return

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return

    # --------------------------------------------------------
    # Respect notification opt-out
    # --------------------------------------------------------

    preference = _get_preference(
        session,
        user_id_int,
    )

    if (
        preference is not None
        and preference.opted_out
    ):
        return

    # --------------------------------------------------------
    # Prevent duplicate notification
    # --------------------------------------------------------

    if notification_exists(
        session,
        user_id=user_id_int,
        ticket_id=str(ticket.id),
    ):
        return

    # --------------------------------------------------------
    # Create learner notification
    # --------------------------------------------------------

    create_feedback_followup_notification(
        session,
        user_id=user_id_int,
        title="Your issue has been escalated",
        message=(
            f"Ticket {ticket.id}: "
            "Your question has been passed to our support team. "
            f"Summary: {ticket.summary}"
        ),
    )


# ============================================================
# Ticket status
# ============================================================

def _is_ticket_resolved(
    ticket: EscalationTicket,
) -> bool:
    """
    Return True when a ticket is resolved or closed.
    """

    status = getattr(
        ticket,
        "status",
        None,
    )

    if status is None:
        return False

    if hasattr(status, "value"):
        status = status.value

    return str(status).lower() in {
        "resolved",
        "closed",
    }


# ============================================================
# Ticket creation date
# ============================================================

def _get_ticket_created_at(
    ticket: EscalationTicket,
) -> datetime | None:
    """
    Safely return the ticket creation timestamp
    normalized to UTC.
    """

    created_at = getattr(
        ticket,
        "created_at",
        None,
    )

    if created_at is None:
        return None

    if created_at.tzinfo is None:
        created_at = created_at.replace(
            tzinfo=timezone.utc
        )

    return created_at


# ============================================================
# Find overdue unresolved tickets
# ============================================================

def get_overdue_unresolved_tickets(
    session: Session,
) -> list[EscalationTicket]:
    """
    Return tickets that:

    1. Are older than two days.
    2. Are not resolved.
    3. Are not closed.
    """

    now = datetime.now(timezone.utc)

    cutoff = now - STAFF_TICKET_AGE

    tickets = session.exec(
        select(EscalationTicket).where(
            EscalationTicket.created_at <= cutoff
        )
    ).all()

    overdue_tickets: list[EscalationTicket] = []

    for ticket in tickets:

        # Never notify staff about completed tickets.
        if _is_ticket_resolved(ticket):
            continue

        created_at = _get_ticket_created_at(ticket)

        if created_at is None:
            continue

        if created_at <= cutoff:
            overdue_tickets.append(ticket)

    return overdue_tickets


# ============================================================
# Find Admin + Program Lead users
# ============================================================

def get_staff_users(
    session: Session,
) -> list[User]:
    """
    Return all Admin and Program Lead users.

    These are the users who should receive notifications
    for overdue unresolved tickets.
    """

    return session.exec(
        select(User).where(
            User.role.in_(
                [
                    UserRole.ADMIN,
                    UserRole.PROGRAM_LEAD,
                ]
            )
        )
    ).all()


# ============================================================
# Notify Admin + Program Lead
# ============================================================

def notify_staff_of_overdue_tickets(
    session: Session,
) -> int:
    """
    Notify every Admin and Program Lead about every
    unresolved ticket older than two days.

    Duplicate notifications are prevented.

    Returns:
        Number of newly created notifications.
    """

    overdue_tickets = get_overdue_unresolved_tickets(
        session
    )

    if not overdue_tickets:
        return 0

    staff_users = get_staff_users(session)

    if not staff_users:
        return 0

    created_count = 0

    for ticket in overdue_tickets:

        # ----------------------------------------------------
        # Only notify Admin + Program Lead.
        # ----------------------------------------------------

        for user in staff_users:

            # ------------------------------------------------
            # Prevent duplicate notification.
            # ------------------------------------------------

            if notification_exists(
                session,
                user_id=user.id,
                ticket_id=str(ticket.id),
            ):
                continue

            reason = getattr(
                ticket,
                "reason",
                "Not provided",
            )

            summary = getattr(
                ticket,
                "summary",
                "No summary provided",
            )

            # ------------------------------------------------
            # Create feedback-followup notification.
            # ------------------------------------------------

            create_feedback_followup_notification(
                session,
                user_id=user.id,
                title="Unresolved ticket requires attention",
                message=(
                    f"Ticket {ticket.id} has remained "
                    "unresolved for more than 2 days. "
                    f"Reason: {reason}. "
                    f"Summary: {summary}"
                ),
            )

            created_count += 1

    return created_count

