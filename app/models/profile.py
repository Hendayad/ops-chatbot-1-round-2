"""Learner profile SQLModel model for database persistence."""

from sqlmodel import Field
from app.models.base import BaseModel


class LearnerProfileRecord(BaseModel, table=True):
    """SQLModel table for persisting learner profiles in Postgres."""

    __tablename__ = "learner_profiles"

    user_id: str = Field(primary_key=True, index=True)
    preferred_name: str | None = Field(default=None, max_length=80)
    # NOTE: the `learner_profiles` table has had a `timezone` column since
    # migration e6a5b8c9d0e1 ("add learner_profile table") -- the column was
    # never missing at the database level. This model class just never
    # exposed it, so PostgresProfileRepository could never read or write it,
    # and the in-chat collector crashed with a KeyError the moment it needed
    # to ask for timezone (ProfileField.TIMEZONE could never be satisfied,
    # since nothing ever persisted it). Adding the field here is the fix;
    # no new migration is required since the column already exists.
    timezone: str | None = Field(default=None, max_length=64)
    cohort: str | None = Field(default=None, max_length=80)
