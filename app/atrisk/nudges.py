"""Proactive at-risk nudge delivery — deduplicated, frequency-capped (PRD F2.4).

Defines an abstract NotificationSender contract so nudge delivery is
decoupled from any specific channel (email/SMS/push/in-app — whichever the
team picks). This keeps the deduplication logic testable in isolation: the
tests substitute an in-memory fake sender instead of hitting a real
provider (per Sarah's suggestion in the team thread).

Actual delivery reuses the existing idempotent notification service
(app.scheduler.runner.run_notification -> app.notifications.service), so
at-risk nudges get the same dedup_key + tenacity retry guarantees that
session/deadline reminders already rely on — no new delivery machinery to
trust.

Frequency cap: rolling, not bucketed. `_nudge_eligible` queries the
learner's most recent SENT AT_RISK_NUDGE notification and compares its
timestamp to now, so "don't nudge more than once per N days" is measured
from the last actual send, not from a fixed calendar bucket. (An earlier
version bucketed by `evaluated_at.toordinal() // frequency_days`, which
allowed two nudges on adjacent calendar days whenever they landed in
different buckets — e.g. day 6 and day 7 with a 7-day window. See the
boundary regression tests in tests/test_atrisk_detection.py.) dedup_key
still exists, but now only guards same-day idempotency (a job retried the
same day reuses the same key instead of reserving a new one) — the actual
frequency enforcement lives entirely in `_nudge_eligible`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlmodel import select

from app.atrisk.detector import DetectionResult
from app.models.notification import NotificationRecord
from app.scheduler.runner import run_notification
from app.schemas.notification import Notification, NotificationPayload, NotificationStatus, NotificationType
from app.services.database import database_service

# F2.4: frequency cap — don't nudge the same learner more than once per this many days.
NUDGE_FREQUENCY_DAYS_DEFAULT = 7


class NotificationSender(ABC):
    """Abstract contract for delivering a single notification through some channel.

    Kept decoupled from the at-risk detection/dedup logic so tests can
    substitute a fake sender instead of a real email/push/SMS provider.
    """

    @abstractmethod
    def send(self, notification: Notification) -> None:
        """Deliver one notification. Raise on failure — the caller retries with backoff."""
        raise NotImplementedError


class NoOpNotificationSender(NotificationSender):
    """Default sender used when no real channel has been wired up yet.

    Delivers nothing externally but still goes through the full
    dedup/persist/retry path, so the job is safe to run before the actual
    notification lane (email/SMS/push) is chosen. Swap in a real sender via
    the `sender` argument on `send_at_risk_nudges` / `run_at_risk_job` once
    F2.1/F2.2's delivery channel is decided.
    """

    def send(self, notification: Notification) -> None:
        """Discard the notification — used before a real delivery channel is wired up."""
        return None


class InMemoryNotificationSender(NotificationSender):
    """Test/dev sender that records every notification actually delivered.

    Used by evals/atrisk_suite.py and tests/test_atrisk_detection.py to
    assert on deduplication without depending on a real notification
    channel.
    """

    def __init__(self) -> None:
        """Start with an empty record of delivered notifications."""
        self.sent: list[Notification] = []

    def send(self, notification: Notification) -> None:
        """Record the notification as delivered instead of calling a real channel."""
        self.sent.append(notification)


def _last_sent_at(learner_id: str) -> Optional[datetime]:
    """Return the timestamp of this learner's most recent SENT at-risk nudge, if any.

    Uses NotificationRecord.created_at as the "sent at" timestamp: in
    practice a record is created and marked SENT within the same delivery
    attempt (see app.notifications.service.send_notification), so
    created_at closely tracks the actual send time without needing a
    dedicated column/migration.
    """
   
    db_service = database_service  # shared singleton -- do not construct a new pool here
    with db_service.get_session_maker() as session:
        record = session.exec(
            select(NotificationRecord)
            .where(
                NotificationRecord.recipient_id == learner_id,
                NotificationRecord.type == NotificationType.AT_RISK_NUDGE,
                NotificationRecord.status == NotificationStatus.SENT,
            )
            .order_by(NotificationRecord.created_at.desc())  # pyright: ignore[reportAttributeAccessIssue]
        ).first()
        if record is None:
            return None
        sent_at = record.created_at
        return sent_at if sent_at.tzinfo is not None else sent_at.replace(tzinfo=UTC)


def _nudge_eligible(learner_id: str, frequency_days: int, now: datetime) -> bool:
    """True if `learner_id` hasn't received a SENT at-risk nudge within the last `frequency_days` days.

    This is a rolling window measured from the actual last send (see
    `_last_sent_at`), not a fixed calendar bucket — see module docstring
    for why the earlier bucket-based approach could send two nudges a
    single calendar day apart.
    """
    last_sent_at = _last_sent_at(learner_id)
    if last_sent_at is None:
        return True
    effective_now = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return (effective_now - last_sent_at) >= timedelta(days=frequency_days)


def build_nudge(result: DetectionResult) -> Notification:
    """Build the deduplicated Notification for one at-risk detection result.

    dedup_key is scoped to the learner + calendar day, so re-running the
    detector job multiple times on the same day (retries, manual re-runs)
    reuses the same reservation instead of creating a new one — this is a
    same-day idempotency guard, not the frequency cap. The actual "don't
    nudge more than once per N days" enforcement happens in
    `_nudge_eligible`, checked by `send_at_risk_nudges` before this
    function is even called.

    Args:
        result: The (at-risk) detection result to build a nudge for.

    Returns:
        A Notification ready to hand to app.scheduler.runner.run_notification.
    """
    dedup_key = f"atrisk:{result.learner_id}:nudge:{result.evaluated_at.date().isoformat()}"
    return Notification(
        recipient_id=result.learner_id,
        type=NotificationType.AT_RISK_NUDGE,
        dedup_key=dedup_key,
        payload=NotificationPayload(
            title="Just checking in",
            body=(
                "We noticed things might be a little tough right now — no judgment at all. "
                "Reach out any time if you'd like a hand getting back on track."
            ),
            metadata={
                "score": result.signals.score,
                "missed_deadlines": result.signals.missed_deadlines,
                "inactive": result.signals.inactive,
                "low_progress": result.signals.low_progress,
                "low_feedback": result.signals.low_feedback,
            },
        ),
    )


def send_at_risk_nudges(
    results: list[DetectionResult],
    *,
    sender: Optional[NotificationSender] = None,
    frequency_days: int = NUDGE_FREQUENCY_DAYS_DEFAULT,
) -> list[Notification]:
    """Send deduplicated, frequency-capped nudges for every at-risk result.

    Only DetectionResults with signals.at_risk=True produce a nudge
    attempt. Before any delivery is attempted, `_nudge_eligible` checks
    whether this learner already received a SENT at-risk nudge within the
    last `frequency_days` days (a real rolling window, not a calendar
    bucket — see module docstring); if so, the notification is returned as
    SKIPPED without ever reaching the sender or the notification service.
    Otherwise delivery goes through the existing idempotent notification
    service + tenacity retry (app.scheduler.runner.run_notification): a
    same-day duplicate dedup_key is skipped rather than resent, and a
    failed delivery is retried with backoff before being marked FAILED
    instead of crashing the batch.

    Args:
        results: Detection results from app.atrisk.detector.run_detector.
        sender: NotificationSender used to actually deliver the nudge.
            Defaults to NoOpNotificationSender.
        frequency_days: Width of the frequency-cap window, in days.

    Returns:
        One Notification (with its final status) per at-risk result. Not
        at-risk results are skipped entirely and produce no entry.
    """
    active_sender = sender or NoOpNotificationSender()
    outcomes: list[Notification] = []
    for result in results:
        if not result.signals.at_risk:
            continue

        notification = build_nudge(result)

        if not _nudge_eligible(result.learner_id, frequency_days, result.evaluated_at):
            notification.status = NotificationStatus.SKIPPED
            outcomes.append(notification)
            continue

        outcomes.append(run_notification(notification, deliver_fn=active_sender.send))
    return outcomes
