from sqlalchemy import Column
from sqlalchemy import Boolean
from sqlmodel import Field

from app.models.base import BaseModel


class UserNotification(BaseModel, table=True):
    """Notifications shown in the learner notification bell."""

    __tablename__ = "user_notification" # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)

    user_id: str = Field(index=True)

    title: str

    message: str

    category: str

    is_read: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False),
    )