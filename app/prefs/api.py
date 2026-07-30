"""Notification preferences API."""

from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.notification_preferences import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
)
from app.services.database import DatabaseService
from app.prefs.model import (
    get_preferences,
    update_preferences,
)

router = APIRouter()

db_service = DatabaseService()


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
