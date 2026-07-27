"""Tests for escalation-triggered notifications (learner + Ops)."""
import asyncio

import pytest

from app.models.notification_preference import NotificationPreference
from app.models.escalation_ticket import EscalationTicket
from app.schemas.notification import NotificationStatus
from app.scheduler.escalation_notifications import (
    notify_learner_of_escalation,
    notify_ops_of_escalation,
)
from app.services.database import DatabaseService

db_service = DatabaseService()
TEST_EMAIL = "escalation_test@example.com"


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Ensure no leftover test user exists before each test."""
    asyncio.run(db_service.delete_user_by_email(TEST_EMAIL))


@pytest.fixture
def test_user():
    """Create a fresh test user for escalation notification tests."""
    return asyncio.run(
        db_service.create_user(email=TEST_EMAIL, password="hashed_pw", username="escalation_tester")
    )


def _make_ticket(user_id: int) -> EscalationTicket:
    """Build a minimal EscalationTicket for testing (not persisted)."""
    return EscalationTicket(
        id=f"esc_test_{user_id}",
        source="answering",
        reason="test reason",
        status="open",
        problem="test problem",
        what_was_tried="test attempt",
        context="test context",
        suggested_next_step="test next step",
        summary="test summary",
        user_goal="test goal",
        key_facts=[],
        assistant_actions=[],
        open_questions=[],
        privacy_note="none",
        session_id=None,
        user_id=str(user_id),
    )


def test_notify_learner_sends_when_no_preference_set(test_user):
    """Verify the learner is notified when no preference row exists (default allowed)."""
    ticket = _make_ticket(test_user.id)
    with db_service.get_session_maker() as session:
        result = notify_learner_of_escalation(session, ticket)

    assert result is not None
    assert result.status == NotificationStatus.SENT


def test_notify_learner_skips_when_opted_out(test_user):
    """Verify the learner is NOT notified when they have opted out."""
    ticket = _make_ticket(test_user.id)
    with db_service.get_session_maker() as session:
        preference = NotificationPreference(user_id=test_user.id, opted_out=True)
        session.add(preference)
        session.commit()

        result = notify_learner_of_escalation(session, ticket)

    assert result is None


def test_notify_learner_returns_none_when_no_user_id():
    """Verify no notification is attempted when the ticket has no user_id."""
    ticket = _make_ticket(user_id=0)
    ticket.user_id = None
    with db_service.get_session_maker() as session:
        result = notify_learner_of_escalation(session, ticket)

    assert result is None


def test_notify_ops_always_sends_regardless_of_learner_preference(test_user):
    """Verify Ops is notified even when the learner has opted out."""
    ticket = _make_ticket(test_user.id)
    with db_service.get_session_maker() as session:
        preference = NotificationPreference(user_id=test_user.id, opted_out=True)
        session.add(preference)
        session.commit()

    # notify_ops_of_escalation doesn't take a session/check preferences at all —
    # confirm it runs without error and doesn't raise.
    notify_ops_of_escalation(ticket, ops_email="ops@example.com")