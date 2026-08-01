from fastapi import APIRouter, Depends
from sqlmodel import select

from app.api.v1.auth import get_current_user
from app.models.reminder_event import ReminderEvent
from app.models.notification_preference import NotificationPreference
from app.services.database import DatabaseService
from app.schemas.notification import NotificationType


router = APIRouter()

db = DatabaseService()


@router.get("")
async def get_my_reminders(
    current_user=Depends(get_current_user)
):

    with db.get_session_maker() as session:

        preferences = session.exec(
            select(NotificationPreference)
            .where(
                NotificationPreference.user_id == str(current_user.id),
                ReminderEvent.type != NotificationType.FEEDBACK_FOLLOWUP
            )
        ).first()


        # No preferences found -> return reminders normally
        if preferences:

            # User disabled everything
            if preferences.opted_out:
                return []


        reminders = session.exec(
            select(ReminderEvent)
            .where(
                ReminderEvent.recipient_id == str(current_user.id)
            )
            .order_by(ReminderEvent.due_at.asc())
        ).all()


        # Filter individual reminder types
        if preferences:

            if not preferences.session_reminders:
                reminders = [
                    r for r in reminders
                    if r.type != NotificationType.SESSION_REMINDER
                ]


            if not preferences.deadline_reminders:
                reminders = [
                    r for r in reminders
                    if r.type != NotificationType.DEADLINE_REMINDER
                ]

            # Was missing entirely — the "Learning nudges" checkbox in
            # Settings saved fine but nothing here ever read it back, so
            # toggling it off had no effect on what this endpoint returned.
            if not preferences.nudges:
                reminders = [
                    r for r in reminders
                    if r.type != NotificationType.NUDGE
                ]
            


    return reminders