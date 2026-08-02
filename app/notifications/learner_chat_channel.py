"""In-chat delivery channel for at-risk learner nudges (PRD F2.4).

Implements ``app.atrisk.nudges.NotificationSender`` by inserting the nudge
as a normal assistant message into the learner's existing LangGraph-backed
chat session -- the only learner-facing surface this codebase has today.
See ``docs/atrisk-nudge-delivery-proposal.md`` for why in-chat was chosen
over email/SMS/push.

Delivery mechanics
-------------------
Chat history for a session is not a plain SQL table: it's the ``messages``
key of a LangGraph checkpointed state, keyed by ``thread_id == session_id``
(see ``app.core.langgraph.graph.LangGraphAgent``). That state key has no
langgraph reducer attached -- ``GraphState`` in ``app/core/langgraph/graph.py``
declares ``messages: list[Any]`` with no ``Annotated[list, add_messages]`` --
so a naive ``graph.aupdate_state(config, {"messages": [nudge]})`` would
REPLACE the whole stored message list with just the nudge, wiping the
learner's real conversation instead of appending to it.

To append safely (and to stay correct even if a reducer is added to
``GraphState`` later), the actual read-modify-write lives in
``LangGraphAgent.append_message`` right next to ``get_chat_history`` --
see that method's docstring for the full explanation. This module just
calls it.

Resolving a learner to a session
---------------------------------
``Notification.recipient_id`` carries an opaque ``learner_id`` (see
``app.schemas.progress.LearnerProgress``) that this codebase does not
otherwise map to a chat ``Session`` anywhere -- ``app/api/v1/atrisk.py``'s
own docstring for ``GET /learners`` says learner_id resolution is left to
"whatever learner-lookup endpoint the platform team already exposes."
Nothing like that exists yet.

``session_resolver`` is a small injectable seam for that lookup, mirroring
the existing ``ProgressProvider`` pattern in ``app.jobs.atrisk_job`` (also
an intentionally-abstracted external dependency). The bundled default,
``default_session_resolver``, assumes the only identity link this repo
actually has today -- ``learner_id == str(User.id)`` -- and picks that
user's most recently created ``Session``. Swap in a real lookup once one
exists; until then, a learner_id that isn't a real user id (e.g. the
fabricated demo ids from ``seed_atrisk_demo_data.py``, "learner_0000") will
correctly fail to resolve rather than silently doing nothing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from langchain_core.messages import AIMessage
from sqlmodel import select

from app.atrisk.nudges import NotificationSender
from app.core.langgraph.graph import LangGraphAgent
from app.core.logging import logger
from app.models.session import Session as ChatSession
from app.schemas.notification import Notification
from app.services.database import database_service

SessionResolver = Callable[[str], Optional[str]]


class NoSessionFoundError(Exception):
    """Raised when no chat session could be resolved for a learner_id.

    Deliberately not swallowed: ``LearnerChatChannel.send`` lets this
    propagate so ``app.scheduler.runner.run_notification`` marks the
    notification FAILED (after its own retries) instead of the job
    silently reporting a nudge as sent when nothing was actually
    delivered.
    """


def default_session_resolver(learner_id: str) -> Optional[str]:
    """Resolve ``learner_id`` to a session id, assuming ``learner_id == str(User.id)``.

    This is the only identity link between the at-risk pipeline and real
    chat users that exists in this codebase today (see module docstring).
    Returns ``None`` if ``learner_id`` isn't an integer-parseable user id,
    or if that user has no chat session yet.
    """
    try:
        user_id = int(learner_id)
    except ValueError:
        return None

    db_service = database_service  # shared singleton -- see app.atrisk.state's module docstring for why
    with db_service.get_session_maker() as db_session:
        row = db_session.exec(
            select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc())
        ).first()
        return row.id if row else None


class LearnerChatChannel(NotificationSender):
    """Delivers at-risk nudges as an assistant message inside a learner's chat."""

    def __init__(
        self,
        session_resolver: Optional[SessionResolver] = None,
        agent: Optional[LangGraphAgent] = None,
    ) -> None:
        """Construct the channel.

        Args:
            session_resolver: Maps learner_id -> session_id (or None if
                unresolvable). Defaults to ``default_session_resolver``.
            agent: The LangGraphAgent to append messages through. Defaults
                to a fresh ``LangGraphAgent()`` -- pass a shared instance
                (e.g. the one already created in ``app.api.v1.chatbot``) to
                reuse its connection pool instead of opening a new one.
        """
        self._resolve_session = session_resolver or default_session_resolver
        self._agent = agent or LangGraphAgent()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Return a persistent event loop, created once per channel instance.

        Earlier this called ``asyncio.run(...)`` per ``send()``, which
        creates and tears down a brand new loop every call. That broke in
        testing: ``LangGraphAgent``'s connection pool is created lazily on
        first use and bound to whichever loop is running at that moment
        (see ``LangGraphAgent._get_connection_pool``), but ``self._agent``
        -- and therefore that pool -- is shared across every ``send()``
        call this channel instance makes (one at-risk job run typically
        calls ``send()`` once per at-risk learner, plus tenacity retries
        each of those up to 3x). Each fresh ``asyncio.run()`` call reused
        the *same* already-created pool under a *new* loop, and on Windows
        specifically that mismatch surfaced as an exception during the
        previous loop's teardown -- even though the actual chat-history
        write had already committed. Tenacity read that as a failure and
        retried, so the exact same nudge got appended to the learner's
        chat two or three times before the whole delivery still ended up
        marked FAILED.

        Keeping one loop (and therefore one connection pool) alive for the
        whole life of this channel instance -- the same lifetime
        ``LangGraphAgent`` itself already assumes when used as a
        long-lived singleton (see ``app.api.v1.chatbot``'s module-level
        ``agent``) -- avoids both the duplicate appends and the wasted
        reconnects.

        ``asyncio.SelectorEventLoop`` specifically (not just "a loop")
        matters on Windows: psycopg's async mode cannot run on the
        default Windows ``ProactorEventLoop``. On other platforms
        ``SelectorEventLoop`` already *is* the default loop, so this has
        no effect there.
        """
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.SelectorEventLoop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def send(self, notification: Notification) -> None:
        """Deliver one nudge. Raises on failure so the caller's retry/backoff kicks in.

        This is a synchronous method (the ``NotificationSender`` contract,
        matching the rest of ``app.atrisk`` and the sync ``run_at_risk_job``
        job runner), but chat delivery is inherently async (LangGraph's
        checkpointer is an ``AsyncPostgresSaver``). Running it via this
        channel's own persistent loop (see ``_get_loop``) is safe
        specifically because ``run_at_risk_job`` is designed to run from a
        plain sync context (a scheduled job/worker), not from inside the
        FastAPI app's own event loop -- do not call this from async
        request-handling code, and do not share one ``LearnerChatChannel``
        instance across threads.
        """
        session_id = self._resolve_session(notification.recipient_id)
        if not session_id:
            raise NoSessionFoundError(
                f"No chat session found for learner_id={notification.recipient_id!r}; cannot deliver in-chat nudge."
            )

        loop = self._get_loop()
        loop.run_until_complete(self._deliver(session_id, notification))

    async def _deliver(self, session_id: str, notification: Notification) -> None:
        nudge_message = AIMessage(
            content=notification.payload.body,
            additional_kwargs={
                "nudge_type": notification.type.value,
                "dedup_key": notification.dedup_key,
            },
        )
        # skip_if_dedup_key makes this idempotent: app.scheduler.runner's
        # tenacity retry can call send() again for the same notification
        # after an already-successful append (e.g. if something *else*
        # raised right after -- see app.core.langgraph.graph.LangGraphAgent
        # .append_message's skip_if_dedup_key docstring for the incident
        # that motivated this), and without this check that would land a
        # second copy of the same nudge in the learner's real chat.
        await self._agent.append_message(session_id, nudge_message, skip_if_dedup_key=notification.dedup_key)
        logger.info(
            "learner_chat_nudge_delivered",
            session_id=session_id,
            recipient_id=notification.recipient_id,
            dedup_key=notification.dedup_key,
        )
