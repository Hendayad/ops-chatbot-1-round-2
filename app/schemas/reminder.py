from datetime import datetime

from pydantic import BaseModel

from app.schemas.notification import NotificationType


class ReminderCreate(BaseModel):
    recipient_id: str
    type: NotificationType
    due_at: datetime
    title: str


class ReminderRead(ReminderCreate):
    id: int