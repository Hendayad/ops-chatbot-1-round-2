"""Chatbot API endpoints for handling chat interactions.

This module provides endpoints for chat interactions, including regular chat,
streaming chat, message history management, chat history clearing, and the
post-response escalation-to-ticket flow.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from app.api.v1.auth import get_current_session
from app.core.config import settings
from app.core.langgraph.graph import LangGraphAgent
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.metrics import llm_stream_duration_seconds
from app.escalation.detector import detect_escalation
from app.models.session import Session
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Message,
    StreamResponse,
)
from app.services.session_naming import maybe_name_session
from app.tickets.service import trigger_answering_escalation
from app.tickets.summary import generate_summary

router = APIRouter()
agent = LangGraphAgent()

_TICKET_ID_RE = re.compile(r"\besc_[A-Za-z0-9_-]+\b")


def _message_text(message: Any) -> str:
    """Return normalized text from a Pydantic message, mapping, or object."""
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")

    return " ".join(content.split()) if isinstance(content, str) else ""


def _assistant_already_escalated(messages: Sequence[Any]) -> bool:
    """Avoid creating a second ticket when the LLM escalation tool already ran."""
    for message in reversed(messages):
        if isinstance(message, dict):
            role = message.get("role") or message.get("type")
        else:
            role = getattr(message, "role", None) or getattr(message, "type", None)

        if role not in {"assistant", "ai"}:
            continue

        text = _message_text(message)
        return bool(_TICKET_ID_RE.search(text)) or "prepared a handoff for the operations team" in text.casefold()

    return False


async def _run_escalation_flow(
    messages: Sequence[Any],
    session: Session,
) -> Message | None:
    """Detect escalation, build a structured summary, and persist a ticket.

    The chat response remains available even if ticket creation fails. The
    learner is told that escalation was successful only when the internal
    ticket service returns a confirmed ticket ID.
    """
    if _assistant_already_escalated(messages):
        logger.info(
            "chat_escalation_skipped_existing_handoff",
            session_id=session.id,
        )
        return None

    decision = detect_escalation({"messages": list(messages)})
    if not decision.should_escalate or decision.trigger is None:
        return None

    trigger = decision.trigger.value
    logger.info(
        "chat_escalation_detected",
        session_id=session.id,
        user_id=str(session.user_id),
        trigger=trigger,
        failure_count=decision.failure_count,
    )

    try:
        handoff = await generate_summary(
            messages,
            trigger=trigger,
            reason=decision.reason,
        )
        ticket = await trigger_answering_escalation(
            reason=decision.reason,
            session_id=session.id,
            user_id=str(session.user_id),
            **handoff.to_service_payload(),
        )

        if ticket.triggered and ticket.ticket_id:
            logger.info(
                "chat_escalation_ticket_created",
                session_id=session.id,
                user_id=str(session.user_id),
                trigger=trigger,
                ticket_id=ticket.ticket_id,
            )
            return Message(
                role="assistant",
                content=(
                    "I've escalated this issue to the Operations team. "
                    f"Your support ticket ID is {ticket.ticket_id}."
                ),
            )

        logger.warning(
            "chat_escalation_ticket_unconfirmed",
            session_id=session.id,
            user_id=str(session.user_id),
            trigger=trigger,
        )
    except Exception as exc:
        logger.exception(
            "chat_escalation_ticket_failed",
            session_id=session.id,
            user_id=str(session.user_id),
            trigger=trigger,
            error_type=type(exc).__name__,
        )

    return Message(
        role="assistant",
        content=(
            "This issue needs help from the Operations team, but I couldn't confirm "
            "that a support ticket was created. Please contact Operations directly."
        ),
    )


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Process a chat request and run the escalation-to-ticket flow."""
    try:
        logger.info(
            "chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        if settings.SESSION_NAMING_ENABLED:
            maybe_name_session(session.id, session.name, chat_request.messages)

        result = await agent.get_response(
            chat_request.messages,
            session.id,
            user_id=str(session.user_id),
            username=session.username,
        )

        escalation_message = await _run_escalation_flow(result, session)
        if escalation_message is not None:
            result.append(escalation_message.model_dump())

        logger.info("chat_request_processed", session_id=session.id)
        return ChatResponse(messages=result)
    except Exception as exc:
        logger.exception(
            "chat_request_failed",
            session_id=session.id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Unable to process the chat request") from exc


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Stream a chat response, then run the escalation-to-ticket flow."""
    try:
        logger.info(
            "stream_chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        if settings.SESSION_NAMING_ENABLED:
            maybe_name_session(session.id, session.name, chat_request.messages)

        async def event_generator():
            """Generate chat chunks followed by an optional escalation message."""
            streamed_chunks: list[str] = []

            try:
                model_name = agent.llm_service.get_llm().get_name()
                with llm_stream_duration_seconds.labels(model=model_name).time():
                    async for chunk in agent.get_stream_response(
                        chat_request.messages,
                        session.id,
                        user_id=str(session.user_id),
                        username=session.username,
                    ):
                        streamed_chunks.append(chunk)
                        response = StreamResponse(content=chunk, done=False)
                        yield f"data: {json.dumps(response.model_dump(mode='json'))}\n\n"

                # Prefer the checkpointed conversation because it contains prior
                # turns required for repeated-failure detection. Fall back to the
                # request plus streamed answer if history retrieval is unavailable.
                try:
                    conversation = await agent.get_chat_history(session.id)
                except Exception:
                    logger.exception(
                        "stream_escalation_history_failed",
                        session_id=session.id,
                    )
                    conversation = [
                        *(message.model_dump() for message in chat_request.messages),
                        {
                            "role": "assistant",
                            "content": "".join(streamed_chunks),
                        },
                    ]

                escalation_message = await _run_escalation_flow(conversation, session)
                if escalation_message is not None:
                    response = StreamResponse(
                        content=f"\n\n{escalation_message.content}",
                        done=False,
                    )
                    yield f"data: {json.dumps(response.model_dump(mode='json'))}\n\n"

                final_response = StreamResponse(content="", done=True)
                yield f"data: {json.dumps(final_response.model_dump(mode='json'))}\n\n"

            except Exception as exc:
                logger.exception(
                    "stream_chat_request_failed",
                    session_id=session.id,
                    error=str(exc),
                )
                error_response = StreamResponse(
                    content="Unable to complete the chat request.",
                    done=True,
                )
                yield f"data: {json.dumps(error_response.model_dump(mode='json'))}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as exc:
        logger.exception(
            "stream_chat_request_failed",
            session_id=session.id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Unable to process the streaming chat request") from exc


@router.get("/messages", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def get_session_messages(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Get all messages for the authenticated session."""
    try:
        messages = await agent.get_chat_history(session.id)
        return ChatResponse(messages=messages)
    except Exception as exc:
        logger.exception(
            "get_messages_failed",
            session_id=session.id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Unable to retrieve chat messages") from exc


@router.delete("/messages")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def clear_chat_history(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Clear all chat history for the authenticated session."""
    try:
        await agent.clear_chat_history(session.id)
        return {"message": "Chat history cleared successfully"}
    except Exception as exc:
        logger.exception(
            "clear_chat_history_failed",
            session_id=session.id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Unable to clear chat history") from exc