"""
Notification API routes.

Notifications are scoped to the currently authenticated user.

All notification categories are returned, including:
    feedback_followup

ReminderEvent records are handled separately.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.user_notification import UserNotification
from app.services.database import database_service


router = APIRouter()


# ============================================================
# GET NOTIFICATIONS
# ============================================================

@router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_user),
):
    """
    Return notifications belonging only to the current user.
    """

    user_id = getattr(
        current_user,
        "id",
        None,
    )

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user has no ID.",
        )

    with database_service.get_session_maker() as session:

        statement = (
            select(UserNotification)
            .where(
                UserNotification.user_id == str(user_id)
            )
            .order_by(
                UserNotification.created_at.desc()
            )
        )

        notifications = session.exec(
            statement
        ).all()

        return [
            {
                "id": notification.id,
                "user_id": notification.user_id,
                "title": notification.title,
                "message": notification.message,
                "category": notification.category,
                "is_read": notification.is_read,
                "created_at": notification.created_at,
            }
            for notification in notifications
        ]


# ============================================================
# MARK NOTIFICATION AS READ
# ============================================================

@router.patch("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
):
    """
    Mark one notification as read.

    A user can only modify their own notification.
    """

    user_id = getattr(
        current_user,
        "id",
        None,
    )

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user has no ID.",
        )

    with database_service.get_session_maker() as session:

        notification = session.exec(
            select(UserNotification).where(
                UserNotification.id == notification_id,
                UserNotification.user_id == str(user_id),
            )
        ).first()

        if notification is None:
            raise HTTPException(
                status_code=404,
                detail="Notification not found.",
            )

        notification.is_read = True

        session.add(notification)
        session.commit()
        session.refresh(notification)

        return {
            "id": notification.id,
            "user_id": notification.user_id,
            "title": notification.title,
            "message": notification.message,
            "category": notification.category,
            "is_read": notification.is_read,
            "created_at": notification.created_at,
        }


# ============================================================
# MARK ALL AS READ
# ============================================================

@router.patch("/read-all")
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
):
    """
    Mark all notifications belonging to the current
    authenticated user as read.
    """

    user_id = getattr(
        current_user,
        "id",
        None,
    )

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user has no ID.",
        )

    with database_service.get_session_maker() as session:

        notifications = session.exec(
            select(UserNotification).where(
                UserNotification.user_id == str(user_id),
                UserNotification.is_read == False,
            )
        ).all()

        for notification in notifications:
            notification.is_read = True
            session.add(notification)

        session.commit()

        return {
            "success": True,
            "updated": len(notifications),
        }

