"""Tests for reminder event scheduling, preference filtering, and dedup."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.models.reminder_event import ReminderEvent
from app.schemas.notification import NotificationStatus, NotificationType
from app.reminders.job import dispatch_due_reminders
from app.services.database import DatabaseService
from sqlalchemy import delete

db_service = DatabaseService()
TEST_EMAIL = "reminders_test@example.com"


@pytest.fixture(autouse=True)
def cleanup_reminder_events():
    """Ensure the reminder_event table is empty before each test."""
    with db_service.get_session_maker() as session:
        session.exec(delete(ReminderEvent))
        session.commit()


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Ensure no leftover test user exists before each test."""
    asyncio.run(db_service.delete_user_by_email(TEST_EMAIL))


@pytest.fixture
def test_user():
    """Create a fresh test user for reminder tests."""
    user = asyncio.run(db_service.create_user(email=TEST_EMAIL, password="hashed_pw", username="reminders_tester"))
    return user


def _create_event(session, recipient_id: str, due_at: datetime, title: str = "Test Event") -> ReminderEvent:
    """Insert a ReminderEvent directly for test setup."""
    event = ReminderEvent(
        recipient_id=recipient_id,
        type=NotificationType.SESSION_REMINDER,
        due_at=due_at,
        title=title,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def test_dispatch_sends_reminder_for_due_event(test_user):
    """Verify a due event within the lead-time window gets a SENT reminder."""
    now = datetime.now(timezone.utc)
    with db_service.get_session_maker() as session:
        _create_event(session, recipient_id=str(test_user.id), due_at=now + timedelta(minutes=30))

        results = dispatch_due_reminders(session, now=now, lead_time=timedelta(hours=1), lead_time_label="1h_before")

    assert len(results) == 1
    assert results[0].status == NotificationStatus.SENT


def test_dispatch_skips_events_outside_lead_time(test_user):
    """Verify an event far in the future is not reminded about yet."""
    now = datetime.now(timezone.utc)
    with db_service.get_session_maker() as session:
        _create_event(session, recipient_id=str(test_user.id), due_at=now + timedelta(days=5))

        results = dispatch_due_reminders(session, now=now, lead_time=timedelta(hours=1), lead_time_label="1h_before")

    assert len(results) == 0


def test_dispatch_does_not_resend_same_event_and_lead_time(test_user):
    """Verify running dispatch twice for the same event/lead-time only sends once."""
    now = datetime.now(timezone.utc)
    with db_service.get_session_maker() as session:
        _create_event(session, recipient_id=str(test_user.id), due_at=now + timedelta(minutes=30))

        first = dispatch_due_reminders(session, now=now, lead_time=timedelta(hours=1), lead_time_label="1h_before")
        second = dispatch_due_reminders(session, now=now, lead_time=timedelta(hours=1), lead_time_label="1h_before")

    assert first[0].status == NotificationStatus.SENT
    assert second[0].status == NotificationStatus.SKIPPED


def test_dispatch_respects_global_opt_out(test_user):
    """Verify a learner who opted out of all notifications receives nothing."""
    from app.models.notification_preference import NotificationPreference

    now = datetime.now(timezone.utc)
    with db_service.get_session_maker() as session:
        preference = NotificationPreference(user_id=test_user.id, opted_out=True)
        session.add(preference)
        session.commit()

        _create_event(session, recipient_id=str(test_user.id), due_at=now + timedelta(minutes=30))

        results = dispatch_due_reminders(session, now=now, lead_time=timedelta(hours=1), lead_time_label="1h_before")

    assert len(results) == 0


def test_dispatch_respects_per_type_opt_out(test_user):
    """Verify a learner who disabled session_reminders specifically receives nothing."""
    from app.models.notification_preference import NotificationPreference

    now = datetime.now(timezone.utc)
    with db_service.get_session_maker() as session:
        preference = NotificationPreference(user_id=test_user.id, session_reminders=False)
        session.add(preference)
        session.commit()

        _create_event(session, recipient_id=str(test_user.id), due_at=now + timedelta(minutes=30))

        results = dispatch_due_reminders(session, now=now, lead_time=timedelta(hours=1), lead_time_label="1h_before")

    assert len(results) == 0


def test_dispatch_sends_deadline_reminder(test_user):
    """Verify a deadline reminder is sent for a due deadline event."""
    now = datetime.now(timezone.utc)

    with db_service.get_session_maker() as session:
        event = ReminderEvent(
            recipient_id=str(test_user.id),
            type=NotificationType.DEADLINE_REMINDER,
            due_at=now + timedelta(minutes=30),
            title="Project Submission",
        )

        session.add(event)
        session.commit()
        session.refresh(event)

        results = dispatch_due_reminders(
            session,
            now=now,
            lead_time=timedelta(hours=1),
            lead_time_label="1h_before",
        )

    assert len(results) == 1
    assert results[0].status == NotificationStatus.SENT
    assert results[0].type == NotificationType.DEADLINE_REMINDER


def test_dispatch_respects_deadline_opt_out(test_user):
    """Verify deadline reminders are suppressed when disabled."""
    from app.models.notification_preference import NotificationPreference

    now = datetime.now(timezone.utc)

    with db_service.get_session_maker() as session:
        preference = NotificationPreference(
            user_id=test_user.id,
            deadline_reminders=False,
        )
        session.add(preference)
        session.commit()

        event = ReminderEvent(
            recipient_id=str(test_user.id),
            type=NotificationType.DEADLINE_REMINDER,
            due_at=now + timedelta(minutes=30),
            title="Project Submission",
        )
        session.add(event)
        session.commit()

        results = dispatch_due_reminders(
            session,
            now=now,
            lead_time=timedelta(hours=1),
            lead_time_label="1h_before",
        )

    assert results == []


def test_send_email_reminder_raises_for_missing_user():
    """Verify send_email_reminder raises when recipient_id has no matching user."""
    from app.scheduler.email_delivery import send_email_reminder
    from app.schemas.notification import Notification, NotificationPayload, NotificationType

    notification = Notification(
        recipient_id="999999",  # unlikely to exist
        type=NotificationType.SESSION_REMINDER,
        payload=NotificationPayload(title="Test", body="Test body"),
        dedup_key="test:email:missing_user",
    )

    with pytest.raises(ValueError, match="No user found"):
        send_email_reminder(notification)


def test_send_email_reminder_raises_for_user_with_no_email(test_user):
    """Verify send_email_reminder raises if the resolved user has no email set."""
    from unittest.mock import patch, AsyncMock
    from app.scheduler.email_delivery import send_email_reminder
    from app.schemas.notification import Notification, NotificationPayload, NotificationType

    notification = Notification(
        recipient_id=str(test_user.id),
        type=NotificationType.SESSION_REMINDER,
        payload=NotificationPayload(title="Test", body="Test body"),
        dedup_key="test:email:no_email",
    )

    fake_user = type(test_user)(id=test_user.id, email="", hashed_password="x")
    with patch("app.scheduler.email_delivery.db_service.get_user", new=AsyncMock(return_value=fake_user)):
        with pytest.raises(ValueError, match="no email address"):
            send_email_reminder(notification)


async def _async_return(value):
    """Helper: wrap a value as an awaitable, for mocking async DB methods."""
    return value
def test_nudge_preference_blocks_nudge():
    """Verify AT_RISK_NUDGE notifications are blocked when nudges=False."""
    from app.prefs.model import NotificationPreference
    from app.schemas.notification import NotificationType
    from app.reminders.job import _is_allowed

    preference = NotificationPreference(
        user_id=1,
        nudges=False,
    )

    assert (
        _is_allowed(preference, NotificationType.AT_RISK_NUDGE)
        is False
    )