"""Learner profile SQLModel model for database persistence."""

from sqlmodel import Field
from app.models.base import BaseModel


class LearnerProfileRecord(BaseModel, table=True):
    """SQLModel table for persisting learner profiles in Postgres."""

    __tablename__ = "learner_profiles"

    user_id: str = Field(primary_key=True, index=True)
    preferred_name: str | None = Field(default=None, max_length=80)
    timezone: str | None = Field(default=None, max_length=64)
    cohort: str | None = Field(default=None, max_length=80)
