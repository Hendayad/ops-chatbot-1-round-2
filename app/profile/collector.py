"""Deterministic in-chat collector for missing learner profile fields.

The collector does not use an LLM to parse personal data. It asks for one
field, validates the reply with Pydantic, and persists only a valid update.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import ValidationError
from sqlmodel import Session, select

from app.models.profile import LearnerProfileRecord
from app.profile.repository import DatabaseProfileRepository
from app.profile.schema import LearnerProfile, ProfileField
from app.services.database import database_service

ProfileLoader = Callable[[str], Awaitable[LearnerProfile]]
ProfileSaver = Callable[[str, LearnerProfile], Awaitable[None]]

_PROMPTS = {
    ProfileField.PREFERRED_NAME: (
        "Before we continue, what name would you like us to use?"
    ),
    # This entry was missing, which meant the collector crashed with a
    # KeyError the moment a learner answered the preferred-name question --
    # TIMEZONE is the very next field in ProfileField's declared order, so
    # every real in-chat collection flow hit this on message two.
    ProfileField.TIMEZONE: (
        "What's your timezone? Please use an IANA name, "
        "like Africa/Cairo or America/New_York."
    ),
    ProfileField.COHORT: (
        "Which program cohort are you in?"
    ),
}


@dataclass(frozen=True)
class CollectionTurn:
    """Result of one learner message through the profile collector."""

    profile: LearnerProfile
    prompt: str | None
    completed: bool
    validation_error: str | None = None


class InMemoryProfileRepository:
    """Small repository used only by tests and local development."""

    def __init__(self) -> None:
        """Initialize the in-memory profile repository."""
        self.profiles: dict[str, LearnerProfile] = {}

    async def load(self, user_id: str) -> LearnerProfile:
        return self.profiles.get(user_id, LearnerProfile())

    async def save(
        self,
        user_id: str,
        profile: LearnerProfile,
    ) -> None:
        self.profiles[user_id] = profile


class PostgresProfileRepository:
    """Production database repository using Postgres/SQLModel."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        """Initialize with database session provider."""
        self._session_factory = session_factory or (
            lambda: Session(database_service.engine))

    async def load(self, user_id: str) -> LearnerProfile:
        """Load learner profile from database or return default empty profile."""
        with self._session_factory() as session:
            record = session.exec(
                select(LearnerProfileRecord).where(
                    LearnerProfileRecord.user_id == str(user_id))
            ).first()
            if not record:
                return LearnerProfile()
            return LearnerProfile(
                preferred_name=record.preferred_name,
                timezone=record.timezone,
                cohort=record.cohort,
            )

    async def save(self, user_id: str, profile: LearnerProfile) -> None:
        """Save or update learner profile in database."""
        with self._session_factory() as session:
            record = session.exec(
                select(LearnerProfileRecord).where(
                    LearnerProfileRecord.user_id == str(user_id))
            ).first()
            if record is None:
                record = LearnerProfileRecord(
                    user_id=str(user_id),
                    preferred_name=profile.preferred_name,
                    timezone=profile.timezone,
                    cohort=profile.cohort,
                )
                session.add(record)
            else:
                record.preferred_name = profile.preferred_name
                record.timezone = profile.timezone
                record.cohort = profile.cohort
                session.add(record)
            session.commit()


class ProfileCollector:
    """Collect required profile fields in a predictable validated sequence."""

    def __init__(
        self,
        load: ProfileLoader,
        save: ProfileSaver,
    ) -> None:
        """Initialize."""
        self._load = load
        self._save = save

    @classmethod
    def with_repository(
        cls, repository: InMemoryProfileRepository | PostgresProfileRepository | DatabaseProfileRepository | None = None
    ) -> "ProfileCollector":
        repo = repository or DatabaseProfileRepository()
        return cls(repo.load, repo.save)

    async def start(self, user_id: str) -> CollectionTurn:
        """Return the first missing-field prompt."""
        profile = await self._load(user_id)
        return self._turn(profile)

    async def accept_reply(
        self,
        user_id: str,
        reply: str,
    ) -> CollectionTurn:
        """Validate and persist one learner reply."""
        profile = await self._load(user_id)

        missing = profile.missing_fields()

        if not missing:
            return CollectionTurn(
                profile=profile,
                prompt=None,
                completed=True,
            )

        field = missing[0]

        try:
            updated = profile.model_copy(
                update={
                    field.value: reply
                }
            )

            updated = LearnerProfile.model_validate(
                updated.model_dump()
            )

        except ValidationError as exc:

            return CollectionTurn(
                profile=profile,
                prompt=_PROMPTS[field],
                completed=False,
                validation_error=exc.errors()[0]["msg"],
            )

        await self._save(user_id, updated)

        return self._turn(updated)

    @staticmethod
    def _turn(profile: LearnerProfile) -> CollectionTurn:

        missing = profile.missing_fields()

        return CollectionTurn(
            profile=profile,
            prompt=_PROMPTS[missing[0]] if missing else None,
            completed=not missing,
        )


def missing_field_detector(
    profile: LearnerProfile,
) -> list[ProfileField]:
    """Return all missing learner profile fields."""
    return profile.missing_fields()


async def inchat_collection_flow(
    user_id: str,
    reply: str | None = None,
    repository: InMemoryProfileRepository | PostgresProfileRepository | DatabaseProfileRepository | None = None,
) -> CollectionTurn:
    """One-field-at-a-time collection flow."""
    repo = repository or DatabaseProfileRepository()
    collector = ProfileCollector.with_repository(repo)

    if reply is None:
        return await collector.start(user_id)

    return await collector.accept_reply(
        user_id,
        reply,
    )


__all__ = [
    "CollectionTurn",
    "InMemoryProfileRepository",
    "PostgresProfileRepository",
    "ProfileCollector",
    "ProfileLoader",
    "ProfileSaver",
    "inchat_collection_flow",
    "missing_field_detector",
]
