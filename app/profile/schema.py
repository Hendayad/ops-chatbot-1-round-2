"""Validated, minimal learner profile data used by the in-chat collector."""

from enum import Enum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator


class ProfileField(str, Enum):
    """Fields collected one at a time so the learner is never overwhelmed."""

    PREFERRED_NAME = "preferred_name"
    TIMEZONE = "timezone"
    COHORT = "cohort"


class LearnerProfile(BaseModel):
    """Privacy-minimal profile persisted for a learner."""

    preferred_name: str | None = Field(default=None, max_length=80)
    timezone: str | None = Field(default=None, max_length=64)
    cohort: str | None = Field(default=None, max_length=80)

    @field_validator("preferred_name", "cohort")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError("must be an IANA timezone such as Africa/Cairo") from exc
        return value

    def missing_fields(self) -> list[ProfileField]:
        """Return fields that still need a validated answer."""
        return [field for field in ProfileField if getattr(self, field.value) is None]
