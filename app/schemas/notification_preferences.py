"""Schemas for notification preferences."""

from pydantic import BaseModel


class NotificationPreferenceResponse(BaseModel):
    """Returned to the frontend."""

    opted_out: bool

    session_reminders: bool

    deadline_reminders: bool

    nudges: bool


class NotificationPreferenceUpdate(BaseModel):
    """Request body for updating preferences."""

    opted_out: bool | None = None

    session_reminders: bool | None = None

    deadline_reminders: bool | None = None

    nudges: bool | None = None