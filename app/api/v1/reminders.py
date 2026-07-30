from fastapi import APIRouter, Depends
from sqlmodel import select

from app.api.v1.auth import get_current_user
from app.models.reminder_event import ReminderEvent
from app.services.database import DatabaseService
from datetime import datetime, timedelta, timezone

router = APIRouter()

db = DatabaseService()


@router.get("")
async def get_my_reminders(current_user=Depends(get_current_user)):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    with db.get_session_maker() as session:
        reminders = session.exec(
            select(ReminderEvent)
            .where(ReminderEvent.recipient_id == str(current_user.id))
            .where(ReminderEvent.due_at >= cutoff)
            .order_by(ReminderEvent.due_at)
        ).all()

    return reminders