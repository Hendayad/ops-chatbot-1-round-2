"""Tests for the in-chat at-risk nudge delivery channel.

Uses fakes for both the session resolver and the LangGraphAgent so these
run without a real Postgres/LangGraph setup -- consistent with how
tests/test_atrisk.py substitutes InMemoryNotificationSender instead of a
real channel.
"""

from __future__ import annotations

import pytest

from app.notifications.learner_chat_channel import (
    LearnerChatChannel,
    NoSessionFoundError,
    default_session_resolver,
)
from app.schemas.notification import Notification, NotificationPayload, NotificationType


class _FakeAgent:
    """Records every message appended, per session_id, without touching LangGraph/Postgres."""

    def __init__(self) -> None:
        self.appended: dict[str, list] = {}

    async def append_message(self, session_id: str, message) -> None:
        self.appended.setdefault(session_id, []).append(message)


def _notification(recipient_id: str = "42") -> Notification:
    return Notification(
        recipient_id=recipient_id,
        type=NotificationType.AT_RISK_NUDGE,
        dedup_key=f"atrisk:{recipient_id}:nudge:1",
        payload=NotificationPayload(title="Just checking in", body="We noticed things might be tough."),
    )


def test_send_resolves_session_and_appends_one_message():
    agent = _FakeAgent()
    channel = LearnerChatChannel(session_resolver=lambda learner_id: "session-abc", agent=agent)

    channel.send(_notification(recipient_id="42"))

    assert list(agent.appended.keys()) == ["session-abc"]
    assert len(agent.appended["session-abc"]) == 1
    assert "tough" in agent.appended["session-abc"][0].content


def test_send_raises_when_no_session_resolves():
    agent = _FakeAgent()
    channel = LearnerChatChannel(session_resolver=lambda learner_id: None, agent=agent)

    with pytest.raises(NoSessionFoundError):
        channel.send(_notification(recipient_id="learner_0000"))

    # Nothing should have been appended anywhere.
    assert agent.appended == {}


def test_default_session_resolver_rejects_non_integer_learner_ids():
    # Fabricated demo learner_ids (e.g. from seed_atrisk_demo_data.py) are not
    # real User ids, so they must fail to resolve rather than silently no-op
    # or raise something unexpected -- this pins that behavior without
    # needing a real DB (int() parsing short-circuits before any query).
    assert default_session_resolver("learner_0000") is None
