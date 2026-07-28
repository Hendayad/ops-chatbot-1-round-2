"""Database model for scheduled reminder events (sessions and deadlines).

ReminderEvent is the scheduler's input contract.

This module does not create reminder events. It consumes ReminderEvent
records produced by the domain responsible for schedulable learner
activities (for example, future learning-session or deadline features).

The reminder scheduler queries these persisted events and applies
notification preferences, deduplication, and delivery.
"""

from datetime import datetime

from sqlmodel import Field

from app.models.base import BaseModel
from app.schemas.notification import NotificationType


class ReminderEvent(BaseModel, table=True):
    """A schedulable event (session or deadline) that may trigger reminders.

    Attributes:
        id: The primary key.
        recipient_id: Learner this event is for.
        type: SESSION_REMINDER or DEADLINE_REMINDER.
        due_at: When the session starts or the deadline is due.
        title: Human-readable label for the event.
        created_at: Inherited from BaseModel.
    """

    id: int = Field(default=None, primary_key=True)
    recipient_id: str = Field(index=True)
    type: NotificationType
    due_at: datetime = Field(index=True)
    title: str
