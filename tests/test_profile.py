"""Tests for the deterministic, validated in-chat profile collector."""

import asyncio

import pytest

from app.profile.collector import InMemoryProfileRepository, ProfileCollector
from app.profile.schema import ProfileField


@pytest.fixture
def collector() -> ProfileCollector:
    return ProfileCollector.with_repository(InMemoryProfileRepository())


def test_collector_asks_one_missing_field_at_a_time(collector: ProfileCollector) -> None:
    first = asyncio.run(collector.start("learner-1"))
    assert first.completed is False
    assert "name" in (first.prompt or "").lower()

    second = asyncio.run(collector.accept_reply("learner-1", "  Ahmed   Magdi "))
    assert second.profile.preferred_name == "Ahmed Magdi"
    assert "timezone" in (second.prompt or "").lower()


def test_collector_rejects_invalid_timezone_without_persisting(collector: ProfileCollector) -> None:
    asyncio.run(collector.accept_reply("learner-1", "Ahmed"))
    invalid = asyncio.run(collector.accept_reply("learner-1", "Cairo time"))

    assert invalid.completed is False
    assert invalid.validation_error is not None
    assert invalid.profile.timezone is None
    assert "IANA" in (invalid.prompt or "")


def test_collector_persists_valid_profile_and_completes(collector: ProfileCollector) -> None:
    asyncio.run(collector.accept_reply("learner-1", "Ahmed"))
    asyncio.run(collector.accept_reply("learner-1", "Africa/Cairo"))
    complete = asyncio.run(collector.accept_reply("learner-1", "Summer 2026"))

    assert complete.completed is True
    assert complete.prompt is None
    assert complete.profile.missing_fields() == []
    assert complete.profile.cohort == "Summer 2026"


def test_profile_schema_has_explicit_collection_order() -> None:
    assert list(ProfileField) == [
        ProfileField.PREFERRED_NAME,
        ProfileField.TIMEZONE,
        ProfileField.COHORT,
    ]


def test_missing_field_detector_and_inchat_collection_flow() -> None:
    from app.profile.collector import inchat_collection_flow, missing_field_detector
    from app.profile.schema import LearnerProfile

    profile = LearnerProfile(preferred_name="Ahmed")
    missing = missing_field_detector(profile)
    assert missing == [ProfileField.TIMEZONE, ProfileField.COHORT]

    repo = InMemoryProfileRepository()
    turn1 = asyncio.run(inchat_collection_flow("user-10", repository=repo))
    assert turn1.completed is False
    assert "name" in (turn1.prompt or "").lower()

    turn2 = asyncio.run(inchat_collection_flow("user-10", reply="Ahmed Magdi", repository=repo))
    assert turn2.profile.preferred_name == "Ahmed Magdi"
    assert "timezone" in (turn2.prompt or "").lower()


def test_postgres_profile_repository() -> None:
    import app.models  # noqa: F401
    from sqlmodel import SQLModel, Session, create_engine
    from app.profile.collector import PostgresProfileRepository
    from app.profile.schema import LearnerProfile

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    def session_factory():
        return Session(engine)

    repo = PostgresProfileRepository(session_factory=session_factory)

    # Initial load returns empty profile
    initial = asyncio.run(repo.load("user-100"))
    assert initial.preferred_name is None

    # Save profile to DB
    profile = LearnerProfile(preferred_name="Sara", timezone="Africa/Cairo", cohort="Fall 2026")
    asyncio.run(repo.save("user-100", profile))

    # Reload profile from DB
    loaded = asyncio.run(repo.load("user-100"))
    assert loaded.preferred_name == "Sara"
    assert loaded.timezone == "Africa/Cairo"
    assert loaded.cohort == "Fall 2026"


