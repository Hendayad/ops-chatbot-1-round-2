"""Notification preference model."""

from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class NotificationPreference(BaseModel, table=True):
    """Stores notification preferences for a learner."""

   

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        unique=True,
        index=True,
        ondelete="CASCADE",
    )

    # Global opt-out
    opted_out: bool = Field(default=False)

    # Individual notification types
    session_reminders: bool = Field(default=True)

    deadline_reminders: bool = Field(default=True)

    nudges: bool = Field(default=True)

    user: "User" = Relationship(back_populates="notification_preference")
