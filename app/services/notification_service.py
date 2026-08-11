"""
Service functions for UserNotification records.

These notifications are displayed in the application notification bell.

All ticket-related notifications use the single category:
    feedback_followup

This module does not create ReminderEvent records.
"""

from sqlmodel import Session, select

from app.models.user_notification import UserNotification


# ============================================================
# Configuration
# ============================================================

FEEDBACK_FOLLOWUP_CATEGORY = "feedback_followup"


# ============================================================
# Create notification
# ============================================================

def create_notification(
    session: Session,
    *,
    user_id: int | str,
    title: str,
    message: str,
    category: str = FEEDBACK_FOLLOWUP_CATEGORY,
) -> UserNotification:
    """
    Create an in-app UserNotification.

    Ticket-related notifications should use the
    feedback_followup category.
    """

    notification = UserNotification(
        user_id=str(user_id),
        title=title,
        message=message,
        category=category,
        is_read=False,
    )

    session.add(notification)
    session.commit()
    session.refresh(notification)

    return notification


# ============================================================
# Check duplicate ticket notification
# ============================================================

def notification_exists(
    session: Session,
    *,
    user_id: int | str,
    ticket_id: str,
) -> bool:
    """
    Check whether a feedback-followup notification for
    this ticket already exists for this user.

    No database schema change is required.
    """

    existing = session.exec(
        select(UserNotification).where(
            UserNotification.user_id == str(user_id),
            UserNotification.category
            == FEEDBACK_FOLLOWUP_CATEGORY,
            UserNotification.message.contains(
                f"Ticket {ticket_id}"
            ),
        )
    ).first()

    return existing is not None


# ============================================================
# Feedback follow-up notification
# ============================================================

def create_feedback_followup_notification(
    session: Session,
    *,
    user_id: int | str,
    title: str,
    message: str,
) -> UserNotification:
    """
    Create a feedback-followup notification.

    This is intentionally stored as UserNotification so
    it appears in the application's notification bell.
    """

    return create_notification(
        session,
        user_id=user_id,
        title=title,
        message=message,
        category=FEEDBACK_FOLLOWUP_CATEGORY,
    )
