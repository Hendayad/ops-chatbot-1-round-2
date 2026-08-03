"""Deterministic in-chat collector for missing learner profile fields.

The collector does not use an LLM to parse personal data. It asks for one
field, validates the reply with Pydantic, and persists only a valid update.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import ValidationError

from app.profile.repository import DatabaseProfileRepository
from app.profile.schema import LearnerProfile, ProfileField

ProfileLoader = Callable[[str], Awaitable[LearnerProfile]]
ProfileSaver = Callable[[str, LearnerProfile], Awaitable[None]]

_PROMPTS = {
    ProfileField.PREFERRED_NAME: (
        "Before we continue, what name would you like us to use?"
    ),
    ProfileField.TIMEZONE: (
        "What is your timezone? Please use an IANA value such as Africa/Cairo."
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
    def with_repository(cls, repository):
        """Create collector from any repository implementing load/save."""
        return cls(repository.load, repository.save)

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
    repository=None,
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
    "ProfileCollector",
    "ProfileLoader",
    "ProfileSaver",
    "inchat_collection_flow",
    "missing_field_detector",
]