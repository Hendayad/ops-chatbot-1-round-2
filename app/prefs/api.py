"""Notification preferences API."""

from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.notification_preferences import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
)
from app.services.database import database_service
from app.prefs.model import (
    get_preferences,
    update_preferences,
)

router = APIRouter()

db_service = database_service  # shared singleton -- do not construct a new pool here


@router.get(
    "/preferences",
    response_model=NotificationPreferenceResponse,
)
async def read_preferences(
    current_user: User = Depends(get_current_user),
):
    with db_service.get_session_maker() as session:
        prefs = get_preferences(session, current_user.id)

        return NotificationPreferenceResponse(
            opted_out=prefs.opted_out,
            session_reminders=prefs.session_reminders,
            deadline_reminders=prefs.deadline_reminders,
            nudges=prefs.nudges,
        )


@router.put(
    "/preferences",
    response_model=NotificationPreferenceResponse,
)
async def edit_preferences(
    payload: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
):
    with db_service.get_session_maker() as session:
        prefs = update_preferences(
            session,
            current_user.id,
            payload,
        )

        return NotificationPreferenceResponse(
            opted_out=prefs.opted_out,
            session_reminders=prefs.session_reminders,
            deadline_reminders=prefs.deadline_reminders,
            nudges=prefs.nudges,
        )


@router.get("")
async def list_notifications(
    current_user: User = Depends(get_current_user),
):
    """List notifications for the current user.

    Minimal stub: the backend has a Notification model and a notification-sending
    service (for nudges, reminders, etc.) but no REST endpoint was ever built to
    expose a user's notification list to the frontend. This returns an empty list
    so the frontend loads without crashing, rather than faking real data. The full
    feature (persisting per-user notifications and listing them here) is separate,
    pre-existing scope -- flag it to the team rather than building it under deadline
    pressure.
    """
    return []


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    """Mark a notification as read.

    Minimal stub matching list_notifications above -- always acknowledges since no
    real per-user notifications are exposed yet.
    """
    return {"id": notification_id, "is_read": True}
