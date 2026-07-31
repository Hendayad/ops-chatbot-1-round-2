"""Escalation trigger interface and default scaffold implementation."""

import logging
from typing import Protocol
from app.notifications.escalation_notifications import notify_learner_of_escalation, notify_ops_of_escalation
from app.services.database import database_service as db_service_for_session
from app.core.config import settings
from app.services.notification_service import create_notification

try:
    from app.core.logging import logger
except ModuleNotFoundError:
    logger = logging.getLogger(__name__)

from app.schemas.escalation import (
    ConversationSummary,
    EscalationSource,
    EscalationTriggerRequest,
    EscalationTriggerResult,
    Ticket,
    TicketStatus,
)


class EscalationTrigger(Protocol):
    """Interface used by answering and proactive flows to escalate issues."""

    async def trigger(self, request: EscalationTriggerRequest) -> EscalationTriggerResult:
        """Trigger human escalation for a validated request."""
        ...


class NoopEscalationTrigger:
    """Scaffold trigger.

    This implementation does not create a real external ticket yet.
    It validates the request, logs the escalation, and returns a stable result.
    """

    async def trigger(self, request: EscalationTriggerRequest) -> EscalationTriggerResult:
        logger.info(
            "escalation_triggered",
            source=request.source.value,
            reason=request.reason,
            status=request.ticket.status.value,
            session_id=request.session_id,
            user_id=request.user_id,
        )

        return EscalationTriggerResult(
            triggered=True,
            status=request.ticket.status,
            ticket_id=None,
            message="Escalation captured by scaffold trigger. No external ticket was created.",
        )


escalation_trigger: EscalationTrigger = NoopEscalationTrigger()


class DatabaseEscalationTrigger:
    """Escalation trigger that persists tickets in the application database."""

    async def trigger(self, request: EscalationTriggerRequest) -> EscalationTriggerResult:
        try:
            from app.services.database import database_service
        except ModuleNotFoundError:
            logger.warning(
                "database_escalation_trigger_dependency_missing",
                source=request.source.value,
                session_id=request.session_id,
                user_id=request.user_id,
            )
            return await NoopEscalationTrigger().trigger(request)

        ticket = await database_service.create_escalation_ticket(
            source=request.source.value,
            reason=request.reason,
            status=request.ticket.status.value,
            problem=request.ticket.problem,
            what_was_tried=request.ticket.what_was_tried,
            context=request.ticket.context,
            suggested_next_step=request.ticket.suggested_next_step,
            summary=request.conversation_summary.summary,
            user_goal=request.conversation_summary.user_goal,
            key_facts=request.conversation_summary.key_facts,
            assistant_actions=request.conversation_summary.assistant_actions,
            open_questions=request.conversation_summary.open_questions,
            privacy_note=request.conversation_summary.privacy_note,
            session_id=request.session_id,
            user_id=request.user_id,
        )

        try:
            with db_service_for_session.get_session_maker() as session:
                    # Learner notification (appears in learner bell)
                create_notification(
                    session=session,
                    user_id=ticket.user_id,
                    title="Escalation Submitted",
                    message=f"Your escalation ticket #{ticket.id} has been created successfully.",
                    category="ticket",
                )

                # Admin notifications (appear in admin bells)
                admin_ids = database_service.get_admin_ids(session)

                for admin_id in admin_ids:
                    create_notification(
                        session=session,
                        user_id=admin_id,
                        title="New Escalation",
                        message=f"A new escalation ticket #{ticket.id} requires review.",
                        category="ticket",
                    )

                notify_learner_of_escalation(session, ticket)


                notify_ops_of_escalation(ticket, ops_email=settings.OPS_NOTIFICATION_EMAIL)

        except Exception:
            logger.exception("escalation_notification_failed", ticket_id=getattr(ticket, "id", None))

        return EscalationTriggerResult(
            triggered=True,
            status=request.ticket.status,
            ticket_id=ticket.id,
            message=f"Escalation stored successfully with ticket ID {ticket.id}.",
        )


escalation_trigger: EscalationTrigger = DatabaseEscalationTrigger()


async def trigger_escalation(request: EscalationTriggerRequest) -> EscalationTriggerResult:
    """Trigger an escalation request through the configured backend."""
    return await escalation_trigger.trigger(request)


async def create_escalation_request(
    *,
    source: EscalationSource,
    reason: str,
    problem: str,
    what_was_tried: str,
    context: str,
    suggested_next_step: str,
    summary: str,
    user_goal: str,
    key_facts: list[str] | None = None,
    assistant_actions: list[str] | None = None,
    open_questions: list[str] | None = None,
    privacy_note: str | None = None,
    status: TicketStatus = TicketStatus.OPEN,
    session_id: str | None = None,
    user_id: str | None = None,
) -> EscalationTriggerRequest:
    """Build a validated escalation request for any caller flow."""
    summary_payload = {
        "summary": summary,
        "user_goal": user_goal,
        "key_facts": key_facts or [],
        "assistant_actions": assistant_actions or [],
        "open_questions": open_questions or [],
    }
    if privacy_note is not None:
        summary_payload["privacy_note"] = privacy_note

    return EscalationTriggerRequest(
        source=source,
        reason=reason,
        ticket=Ticket(
            problem=problem,
            what_was_tried=what_was_tried,
            context=context,
            suggested_next_step=suggested_next_step,
            status=status,
        ),
        conversation_summary=ConversationSummary(**summary_payload),
        session_id=session_id,
        user_id=user_id,
    )


async def trigger_answering_escalation(
    *,
    reason: str,
    problem: str,
    what_was_tried: str,
    context: str,
    suggested_next_step: str,
    summary: str,
    user_goal: str,
    key_facts: list[str] | None = None,
    assistant_actions: list[str] | None = None,
    open_questions: list[str] | None = None,
    privacy_note: str | None = None,
    status: TicketStatus = TicketStatus.OPEN,
    session_id: str | None = None,
    user_id: str | None = None,
) -> EscalationTriggerResult:
    """Build and trigger an answering-flow escalation."""
    request = await create_escalation_request(
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
    return await trigger_escalation(request)


async def trigger_proactive_escalation(
    *,
    reason: str,
    problem: str,
    what_was_tried: str,
    context: str,
    suggested_next_step: str,
    summary: str,
    user_goal: str,
    key_facts: list[str] | None = None,
    assistant_actions: list[str] | None = None,
    open_questions: list[str] | None = None,
    privacy_note: str | None = None,
    status: TicketStatus = TicketStatus.OPEN,
    session_id: str | None = None,
    user_id: str | None = None,
) -> EscalationTriggerResult:
    """Build and trigger a proactive-flow escalation."""
    request = await create_escalation_request(
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
    return await trigger_escalation(request)
