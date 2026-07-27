from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.models.reminder_event import ReminderEvent
from app.schemas.reminder import ReminderCreate, ReminderRead
from app.services.database import get_session

router = APIRouter()


@router.post("", response_model=ReminderRead)
def create_reminder(
    reminder: ReminderCreate,
    session: Session = Depends(get_session),
):
    event = ReminderEvent(
        recipient_id=reminder.recipient_id,
        type=reminder.type,
        due_at=reminder.due_at,
        title=reminder.title,
    )

    session.add(event)
    session.commit()
    session.refresh(event)

    return event