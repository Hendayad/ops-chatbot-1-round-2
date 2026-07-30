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
