"""
Ticket persistence, lookup, status management, and notifications.

This module is the application service for escalation tickets.

Notification rules:

LEARNER
    - Receives an immediate notification when their issue is escalated.
    - Learner notification preferences are respected.

ADMIN / PROGRAM_LEAD
    - Receive a notification when an unresolved ticket is older than 2 days.
    - Staff notifications are handled separately by
      app.notifications.escalation_notifications.

This service is responsible for:
    1. Persisting escalation tickets.
    2. Creating learner notifications immediately after ticket creation.
    3. Notifying Operations through the configured Ops notifier.
    4. Listing, retrieving, and resolving tickets.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from prometheus_client import Counter, Histogram
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, select
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import logger
from app.metrics.kpis import (
    DEFAULT_COHORT_LABEL,
    track_connector_failure,
    track_escalation,
    track_resolution_time,
    track_ticket_created,
    update_at_risk_count,
)
from app.models.escalation_ticket import EscalationTicket
from app.models.notification_preference import NotificationPreference
from app.models.user import User
from app.schemas.escalation import (
    ConversationSummary,
    EscalationSource,
    EscalationTriggerRequest,
    EscalationTriggerResult,
    Ticket,
    TicketStatus,
)
from app.services.database import DatabaseService, database_service
from app.services.notification_service import (
    create_feedback_followup_notification,
    notification_exists,
)


# ============================================================
# Configuration
# ============================================================

_MAX_PAGE_SIZE = 100
_RETRY_ATTEMPTS = 3


# ============================================================
# Metrics
# ============================================================

ticket_service_operations_total = Counter(
    "ticket_service_operations_total",
    "Ticket-service operations grouped by operation and outcome.",
    ["operation", "outcome"],
)

ticket_service_duration_seconds = Histogram(
    "ticket_service_duration_seconds",
    "Time spent performing ticket-service operations.",
    ["operation"],
    buckets=[
        0.005,
        0.01,
        0.05,
        0.1,
        0.3,
        0.5,
        1.0,
        2.0,
        5.0,
    ],
)

ops_ticket_notifications_total = Counter(
    "ops_ticket_notifications_total",
    "Operations ticket notifications grouped by outcome.",
    ["outcome"],
)

learner_ticket_notifications_total = Counter(
    "learner_ticket_notifications_total",
    "Learner ticket notifications grouped by outcome.",
    ["outcome"],
)


# ============================================================
# Exceptions
# ============================================================

class TicketServiceError(RuntimeError):
    """Base exception for ticket-service failures."""


class TicketNotFoundError(TicketServiceError):
    """Raised when the requested ticket does not exist."""

    def __init__(self, ticket_id: str) -> None:
        """Initialize the exception with the missing ticket identifier."""
        super().__init__(f"Ticket {ticket_id!r} was not found.")
        self.ticket_id = ticket_id


# ============================================================
# Operations notification contract
# ============================================================

@dataclass(frozen=True, slots=True)
class OpsTicketNotification:
    """Minimal privacy-preserving payload sent to Operations."""

    ticket_id: str
    source: str
    status: str
    problem: str
    summary: str
    suggested_next_step: str


class OpsNotifier(Protocol):
    """Contract implemented by an Operations notification adapter."""

    def notify_ticket_created(
        self,
        notification: OpsTicketNotification,
    ) -> Awaitable[None] | None:
        """Notify Operations that a support ticket was created."""
        ...


class LoggingOpsNotifier:
    """
    Default notification adapter that emits the notification
    contract to logs.
    """

    def notify_ticket_created(
        self,
        notification: OpsTicketNotification,
    ) -> None:
        """Emit a structured Operations notification event."""

        logger.info(
            "ops_ticket_notification",
            ticket_id=notification.ticket_id,
            source=notification.source,
            status=notification.status,
            problem=notification.problem,
            summary=notification.summary,
            suggested_next_step=notification.suggested_next_step,
        )


# ============================================================
# Ticket Service
# ============================================================

class TicketService:
    """Coordinate ticket persistence and notifications."""

    def __init__(
        self,
        *,
        database: DatabaseService | None = None,
        notifier: OpsNotifier | None = None,
    ) -> None:
        """Initialize the service with replaceable dependencies."""

        self._database = database or database_service
        self._notifier = notifier or LoggingOpsNotifier()

    # ========================================================
    # CREATE TICKET
    # ========================================================

    async def create_ticket(
        self,
        request: EscalationTriggerRequest,
    ) -> EscalationTriggerResult:
        """
        Persist one validated escalation request.

        After the ticket is persisted:

            1. Create an immediate learner notification.
            2. Notify Operations.

        Notification failures do not delete or invalidate the ticket.
        """

        operation = "create"

        ticket = self._record_from_request(request)

        # ----------------------------------------------------
        # Persist ticket
        # ----------------------------------------------------

        try:
            with ticket_service_duration_seconds.labels(
                operation=operation
            ).time():

                stored = await self._persist_ticket(ticket)

            ticket_service_operations_total.labels(
                operation=operation,
                outcome="success",
            ).inc()

        except Exception:
            ticket_service_operations_total.labels(
                operation=operation,
                outcome="error",
            ).inc()

            logger.exception(
                "ticket_creation_failed",
                source=request.source.value,
                session_id=request.session_id,
                user_id=request.user_id,
            )

            raise

        # ====================================================
        # IMPORTANT:
        # Notify learner immediately after ticket creation.
        # ====================================================

        learner_notification_delivered = (
            await self._notify_learner(stored)
        )

        # ====================================================
        # Notify Operations
        # ====================================================

        notification_delivered = await self._notify_ops(stored)

        # ====================================================
        # M09 Instrumentation
        # ====================================================

        cohort_id = getattr(
            request,
            "cohort_id",
            DEFAULT_COHORT_LABEL,
        )

        track_ticket_created(
            cohort_id,
            severity=stored.source,
        )

        track_escalation(
            cohort_id,
            reason=request.reason,
        )

        if getattr(request, "is_at_risk", False):
            update_at_risk_count(
                cohort_id,
                "high",
                1,
            )

        # ====================================================
        # Result message
        # ====================================================

        if (
            notification_delivered
            and learner_notification_delivered
        ):
            message = (
                f"Escalation stored successfully with "
                f"ticket ID {stored.id}. "
                "The learner and Operations were notified."
            )

        elif learner_notification_delivered:
            message = (
                f"Escalation stored with ticket ID "
                f"{stored.id}. "
                "The learner was notified, but the "
                "Operations notification could not be confirmed."
            )

        elif notification_delivered:
            message = (
                f"Escalation stored with ticket ID "
                f"{stored.id}. "
                "Operations was notified, but the learner "
                "notification could not be confirmed."
            )

        else:
            message = (
                f"Escalation stored with ticket ID "
                f"{stored.id}; learner and Operations "
                "notifications could not be confirmed."
            )

        return EscalationTriggerResult(
            triggered=True,
            status=TicketStatus(stored.status),
            ticket_id=stored.id,
            message=message,
        )

    # ========================================================
    # LEARNER NOTIFICATION
    # ========================================================

    async def _notify_learner(
        self,
        ticket: EscalationTicket,
    ) -> bool:
        """
        Create an immediate feedback-followup notification
        for the learner after an escalation ticket is created.

        The actual notification logic is handled by
        notify_learner_of_escalation() so that there is one
        source of truth for:

        - learner notification preferences
        - duplicate detection
        - feedback_followup notification creation

        Returns:
            True if the notification was successfully created
            or already existed.

            False if the notification was skipped or failed.
        """

        user_id = getattr(
            ticket,
            "user_id",
            None,
        )

        if user_id is None:
            learner_ticket_notifications_total.labels(
                outcome="missing_user"
            ).inc()

            logger.warning(
                "learner_notification_skipped_missing_user",
                ticket_id=ticket.id,
            )

            return False

        try:
            user_id_int = int(user_id)

        except (TypeError, ValueError):

            learner_ticket_notifications_total.labels(
                outcome="invalid_user"
            ).inc()

            logger.warning(
                "learner_notification_skipped_invalid_user",
                ticket_id=ticket.id,
                user_id=user_id,
            )

            return False

        try:
            # ------------------------------------------------
            # Use the central escalation notification service.
            #
            # This function:
            #
            # 1. Checks learner notification preferences.
            # 2. Prevents duplicate notifications.
            # 3. Creates feedback_followup notification.
            #
            # notify_learner_of_escalation() needs an actual
            # SQLModel Session, not a session-maker -- open one
            # from self._database (same pattern used by
            # app.services.escalation.DatabaseEscalationTrigger)
            # rather than calling a session getter that doesn't
            # exist on this class.
            # ------------------------------------------------

            with self._database.get_session_maker() as session:
                notify_learner_of_escalation(
                    session,
                    ticket,
                )

            learner_ticket_notifications_total.labels(
                outcome="success"
            ).inc()

            logger.info(
                "learner_ticket_notification_created",
                ticket_id=ticket.id,
                user_id=user_id_int,
            )

            return True

        except Exception:
            learner_ticket_notifications_total.labels(
                outcome="error"
            ).inc()

            logger.exception(
                "learner_ticket_notification_failed",
                ticket_id=ticket.id,
                user_id=user_id_int,
            )

            # The ticket already exists, so notification failure
            # must not cause ticket creation to fail.
            return False


    # ========================================================
    # LIST TICKETS
    # ========================================================

    async def list_tickets(
        self,
        *,
        status: TicketStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[EscalationTicket]:
        """Return tickets newest first, optionally filtered."""

        if offset < 0:
            raise ValueError(
                "offset must be zero or greater"
            )

        if not 1 <= limit <= _MAX_PAGE_SIZE:
            raise ValueError(
                f"limit must be between 1 and {_MAX_PAGE_SIZE}"
            )

        operation = "list"

        try:
            with ticket_service_duration_seconds.labels(
                operation=operation
            ).time():

                tickets = await self._list_tickets(
                    status=status,
                    offset=offset,
                    limit=limit,
                )

            ticket_service_operations_total.labels(
                operation=operation,
                outcome="success",
            ).inc()

            return tickets

        except Exception:
            ticket_service_operations_total.labels(
                operation=operation,
                outcome="error",
            ).inc()

            logger.exception(
                "ticket_list_failed",
                status=(
                    status.value
                    if status is not None
                    else None
                ),
                offset=offset,
                limit=limit,
            )

            raise

    # ========================================================
    # GET TICKET
    # ========================================================

    async def get_ticket(
        self,
        ticket_id: str,
    ) -> EscalationTicket:
        """Return one ticket or raise TicketNotFoundError."""

        normalized_id = self._normalize_ticket_id(
            ticket_id
        )

        operation = "get"

        try:
            with ticket_service_duration_seconds.labels(
                operation=operation
            ).time():

                ticket = await self._get_ticket(
                    normalized_id
                )

            if ticket is None:
                ticket_service_operations_total.labels(
                    operation=operation,
                    outcome="not_found",
                ).inc()

                raise TicketNotFoundError(
                    normalized_id
                )

            ticket_service_operations_total.labels(
                operation=operation,
                outcome="success",
            ).inc()

            return ticket

        except TicketNotFoundError:
            raise

        except Exception:
            ticket_service_operations_total.labels(
                operation=operation,
                outcome="error",
            ).inc()

            logger.exception(
                "ticket_get_failed",
                ticket_id=normalized_id,
            )

            raise

    # ========================================================
    # RESOLVE TICKET
    # ========================================================

    async def resolve_ticket(
        self,
        ticket_id: str,
    ) -> EscalationTicket:
        """Mark a ticket resolved and return the updated record."""

        normalized_id = self._normalize_ticket_id(
            ticket_id
        )

        operation = "resolve"

        try:
            with ticket_service_duration_seconds.labels(
                operation=operation
            ).time():

                ticket = await self._resolve_ticket(
                    normalized_id
                )

            if ticket is None:
                ticket_service_operations_total.labels(
                    operation=operation,
                    outcome="not_found",
                ).inc()

                raise TicketNotFoundError(
                    normalized_id
                )

            ticket_service_operations_total.labels(
                operation=operation,
                outcome="success",
            ).inc()

            # ------------------------------------------------
            # M09 Resolution Time
            # ------------------------------------------------

            if getattr(ticket, "created_at", None):

                now = datetime.now(timezone.utc)

                created_at = ticket.created_at

                if created_at.tzinfo is None:
                    created_at = created_at.replace(
                        tzinfo=timezone.utc
                    )

                duration_seconds = (
                    now - created_at
                ).total_seconds()

                cohort_id = getattr(
                    ticket,
                    "cohort_id",
                    DEFAULT_COHORT_LABEL,
                )

                track_resolution_time(
                    cohort_id,
                    duration_seconds,
                )

            return ticket

        except TicketNotFoundError:
            raise

        except Exception:
            ticket_service_operations_total.labels(
                operation=operation,
                outcome="error",
            ).inc()

            logger.exception(
                "ticket_resolve_failed",
                ticket_id=normalized_id,
            )

            raise

    # ========================================================
    # BUILD DATABASE RECORD
    # ========================================================

    @staticmethod
    def _record_from_request(
        request: EscalationTriggerRequest,
    ) -> EscalationTicket:
        """Convert validated request into database record."""

        ticket = request.ticket
        summary = request.conversation_summary

        return EscalationTicket(
            id=f"esc_{uuid4().hex[:12]}",
            source=request.source.value,
            reason=request.reason,
            status=ticket.status.value,
            problem=ticket.problem,
            what_was_tried=ticket.what_was_tried,
            context=ticket.context,
            suggested_next_step=ticket.suggested_next_step,
            summary=summary.summary,
            user_goal=summary.user_goal,
            key_facts=list(summary.key_facts),
            assistant_actions=list(
                summary.assistant_actions
            ),
            open_questions=list(
                summary.open_questions
            ),
            privacy_note=summary.privacy_note,
            session_id=request.session_id,
            user_id=request.user_id,
        )

    # ========================================================
    # OPS NOTIFICATION PAYLOAD
    # ========================================================

    @staticmethod
    def _notification_from_ticket(
        ticket: EscalationTicket,
    ) -> OpsTicketNotification:
        """Build the privacy-preserving Operations payload."""

        return OpsTicketNotification(
            ticket_id=ticket.id,
            source=ticket.source,
            status=ticket.status,
            problem=ticket.problem,
            summary=ticket.summary,
            suggested_next_step=ticket.suggested_next_step,
        )

    # ========================================================
    # NORMALIZE TICKET ID
    # ========================================================

    @staticmethod
    def _normalize_ticket_id(
        ticket_id: str,
    ) -> str:
        """Validate and normalize a ticket ID."""

        normalized = ticket_id.strip()

        if not normalized:
            raise ValueError(
                "ticket_id must not be empty"
            )

        return normalized

    # ========================================================
    # PERSIST TICKET
    # ========================================================

    @retry(
        retry=retry_if_exception_type(
            SQLAlchemyError
        ),
        stop=stop_after_attempt(
            _RETRY_ATTEMPTS
        ),
        wait=wait_exponential(
            multiplier=0.05,
            min=0.05,
            max=0.5,
        ),
        reraise=True,
    )
    async def _persist_ticket(
        self,
        ticket: EscalationTicket,
    ) -> EscalationTicket:
        """Persist a stable-ID ticket safely."""

        with self._database.get_session_maker() as session:

            existing = session.get(
                EscalationTicket,
                ticket.id,
            )

            if existing is not None:
                return existing

            session.add(ticket)
            session.commit()
            session.refresh(ticket)

            logger.info(
                "ticket_created",
                ticket_id=ticket.id,
                source=ticket.source,
                status=ticket.status,
                session_id=ticket.session_id,
                user_id=ticket.user_id,
            )

            return ticket

    # ========================================================
    # LIST DATABASE TICKETS
    # ========================================================

    @retry(
        retry=retry_if_exception_type(
            SQLAlchemyError
        ),
        stop=stop_after_attempt(
            _RETRY_ATTEMPTS
        ),
        wait=wait_exponential(
            multiplier=0.05,
            min=0.05,
            max=0.5,
        ),
        reraise=True,
    )
    async def _list_tickets(
        self,
        *,
        status: TicketStatus | None,
        offset: int,
        limit: int,
    ) -> list[EscalationTicket]:
        """Execute paginated ticket query."""

        with self._database.get_session_maker() as session:

            statement = select(
                EscalationTicket
            )

            if status is not None:
                statement = statement.where(
                    EscalationTicket.status
                    == status.value
                )

            statement = (
                statement
                .order_by(
                    col(
                        EscalationTicket.created_at
                    ).desc()
                )
                .offset(offset)
                .limit(limit)
            )

            return list(
                session.exec(statement).all()
            )

    # ========================================================
    # GET DATABASE TICKET
    # ========================================================

    @retry(
        retry=retry_if_exception_type(
            SQLAlchemyError
        ),
        stop=stop_after_attempt(
            _RETRY_ATTEMPTS
        ),
        wait=wait_exponential(
            multiplier=0.05,
            min=0.05,
            max=0.5,
        ),
        reraise=True,
    )
    async def _get_ticket(
        self,
        ticket_id: str,
    ) -> EscalationTicket | None:
        """Read one ticket."""

        with self._database.get_session_maker() as session:
            return session.get(
                EscalationTicket,
                ticket_id,
            )

    # ========================================================
    # RESOLVE DATABASE TICKET
    # ========================================================

    @retry(
        retry=retry_if_exception_type(
            SQLAlchemyError
        ),
        stop=stop_after_attempt(
            _RETRY_ATTEMPTS
        ),
        wait=wait_exponential(
            multiplier=0.05,
            min=0.05,
            max=0.5,
        ),
        reraise=True,
    )
    async def _resolve_ticket(
        self,
        ticket_id: str,
    ) -> EscalationTicket | None:
        """Set a stored ticket to resolved."""

        with self._database.get_session_maker() as session:

            ticket = session.get(
                EscalationTicket,
                ticket_id,
            )

            if ticket is None:
                return None

            if (
                ticket.status
                != TicketStatus.RESOLVED.value
            ):
                ticket.status = (
                    TicketStatus.RESOLVED.value
                )

                session.add(ticket)
                session.commit()
                session.refresh(ticket)

                logger.info(
                    "ticket_resolved",
                    ticket_id=ticket.id,
                )

            return ticket

    # ========================================================
    # OPS NOTIFICATION DELIVERY
    # ========================================================

    @retry(
        stop=stop_after_attempt(
            _RETRY_ATTEMPTS
        ),
        wait=wait_exponential(
            multiplier=0.05,
            min=0.05,
            max=0.5,
        ),
        reraise=True,
    )
    async def _deliver_notification(
        self,
        notification: OpsTicketNotification,
    ) -> None:
        """Deliver notification through sync or async adapter."""

        result = (
            self._notifier.notify_ticket_created(
                notification
            )
        )

        if inspect.isawaitable(result):
            await result

    async def _notify_ops(
        self,
        ticket: EscalationTicket,
    ) -> bool:
        """Notify Operations without invalidating the ticket."""

        notification = (
            self._notification_from_ticket(
                ticket
            )
        )

        try:
            await self._deliver_notification(
                notification
            )

            ops_ticket_notifications_total.labels(
                outcome="success"
            ).inc()

            return True

        except Exception:
            ops_ticket_notifications_total.labels(
                outcome="error"
            ).inc()

            track_connector_failure(
                type(self._notifier).__name__
            )

            logger.exception(
                "ops_ticket_notification_failed",
                ticket_id=ticket.id,
            )

            return False


# ============================================================
# Default service
# ============================================================

_default_ticket_service = TicketService()


# ============================================================
# Public service functions
# ============================================================

async def create_ticket(
    request: EscalationTriggerRequest,
) -> EscalationTriggerResult:
    """Persist and notify for an escalation request."""

    return await _default_ticket_service.create_ticket(
        request
    )


async def list_tickets(
    *,
    status: TicketStatus | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[EscalationTicket]:
    """List tickets through the default service."""

    return await _default_ticket_service.list_tickets(
        status=status,
        offset=offset,
        limit=limit,
    )


async def get_ticket(
    ticket_id: str,
) -> EscalationTicket:
    """Fetch one ticket."""

    return await _default_ticket_service.get_ticket(
        ticket_id
    )


async def resolve_ticket(
    ticket_id: str,
) -> EscalationTicket:
    """Resolve one ticket."""

    return await _default_ticket_service.resolve_ticket(
        ticket_id
    )


# ============================================================
# Request builder
# ============================================================

def _build_request(
    *,
    source: EscalationSource,
    reason: str,
    problem: str,
    what_was_tried: str,
    context: str,
    suggested_next_step: str,
    summary: str,
    user_goal: str,
    key_facts: Sequence[str] | None = None,
    assistant_actions: Sequence[str] | None = None,
    open_questions: Sequence[str] | None = None,
    privacy_note: str | None = None,
    status: TicketStatus = TicketStatus.OPEN,
    session_id: str | None = None,
    user_id: str | None = None,
) -> EscalationTriggerRequest:
    """Build the validated escalation request."""

    summary_values: dict[str, object] = {
        "summary": summary,
        "user_goal": user_goal,
        "key_facts": list(
            key_facts or ()
        ),
        "assistant_actions": list(
            assistant_actions or ()
        ),
        "open_questions": list(
            open_questions or ()
        ),
    }

    if privacy_note is not None:
        summary_values["privacy_note"] = (
            privacy_note
        )

    return EscalationTriggerRequest(
        source=source,
        reason=reason,
        ticket=Ticket.model_validate(
            {
                "problem": problem,
                "what_was_tried": what_was_tried,
                "context": context,
                "suggested_next_step": (
                    suggested_next_step
                ),
                "status": status,
            }
        ),
        conversation_summary=ConversationSummary.model_validate(
            summary_values
        ),
        session_id=session_id,
        user_id=user_id,
    )


# ============================================================
# Answering escalation
# ============================================================

async def trigger_answering_escalation(
    *,
    reason: str,
    problem: str,
    what_was_tried: str,
    context: str,
    suggested_next_step: str,
    summary: str,
    user_goal: str,
    key_facts: Sequence[str] | None = None,
    assistant_actions: Sequence[str] | None = None,
    open_questions: Sequence[str] | None = None,
    privacy_note: str | None = None,
    status: TicketStatus = TicketStatus.OPEN,
    session_id: str | None = None,
    user_id: str | None = None,
) -> EscalationTriggerResult:
    """Create a ticket from answering escalation flow."""

    request = _build_request(
        source=EscalationSource.ANSWERING,
        reason=reason,
        problem=problem,
        what_was_tried=what_was_tried,
        context=context,
        suggested_next_step=suggested_next_step,
        summary=summary,
        user_goal=user_goal,
        key_facts=key_facts,
        assistant_actions=assistant_actions,
        open_questions=open_questions,
        privacy_note=privacy_note,
        status=status,
        session_id=session_id,
        user_id=user_id,
    )

    return await create_ticket(request)


# ============================================================
# Proactive escalation
# ============================================================

async def trigger_proactive_escalation(
    *,
    reason: str,
    problem: str,
    what_was_tried: str,
    context: str,
    suggested_next_step: str,
    summary: str,
    user_goal: str,
    key_facts: Sequence[str] | None = None,
    assistant_actions: Sequence[str] | None = None,
    open_questions: Sequence[str] | None = None,
    privacy_note: str | None = None,
    status: TicketStatus = TicketStatus.OPEN,
    session_id: str | None = None,
    user_id: str | None = None,
) -> EscalationTriggerResult:
    """Create a ticket from proactive workflow."""

    request = _build_request(
        source=EscalationSource.PROACTIVE,
        reason=reason,
        problem=problem,
        what_was_tried=what_was_tried,
        context=context,
        suggested_next_step=suggested_next_step,
        summary=summary,
        user_goal=user_goal,
        key_facts=key_facts,
        assistant_actions=assistant_actions,
        open_questions=open_questions,
        privacy_note=privacy_note,
        status=status,
        session_id=session_id,
        user_id=user_id,
    )

    return await create_ticket(request)


__all__ = [
    "LoggingOpsNotifier",
    "OpsNotifier",
    "OpsTicketNotification",
    "TicketNotFoundError",
    "TicketService",
    "TicketServiceError",
    "create_ticket",
    "get_ticket",
    "list_tickets",
    "resolve_ticket",
    "trigger_answering_escalation",
    "trigger_proactive_escalation",
]

