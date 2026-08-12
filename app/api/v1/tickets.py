"""Authenticated, rate-limited Operations APIs for escalation tickets."""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.v1.auth import get_current_ops_user
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.escalation_ticket import EscalationTicket
from app.models.user import User
from app.schemas.base import BaseResponse
from app.schemas.escalation import EscalationSource, TicketStatus
from app.services.database import database_service
from app.tickets.service import (
    TicketNotFoundError,
    TicketServiceError,
    get_ticket as get_ticket_from_service,
    list_tickets as list_tickets_from_service,
    resolve_ticket as resolve_ticket_from_service,
)

router = APIRouter()
db_service = database_service

_TICKET_RATE_LIMIT = settings.RATE_LIMIT_ENDPOINTS.get(
    "tickets",
    ["60 per minute"],
)[0]


class OpsTicket(BaseModel):
    """Privacy-preserving ticket representation returned to Operations."""

    ticket_id: str
    source: EscalationSource
    reason: str
    status: TicketStatus
    problem: str
    what_was_tried: str
    context: str
    suggested_next_step: str
    summary: str
    user_goal: str
    key_facts: list[str] = Field(default_factory=list)
    assistant_actions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    privacy_note: str

    session_id: str | None = None

    # Ticket ownership / learner identity.
    user_id: str | None = None
    learner_name: str = "Unknown learner"

    created_at: datetime


class TicketListResponse(BaseResponse):
    """Paginated collection returned by the ticket-list endpoint."""

    tickets: list[OpsTicket]
    offset: int
    limit: int
    returned: int


class TicketDetailResponse(BaseResponse):
    """Single-ticket response used by view and resolve endpoints."""

    ticket: OpsTicket


def _display_name(user: User) -> str:
    """Build the learner's current full name with safe fallbacks."""
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()

    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name

    username = (user.username or "").strip()
    if username:
        return username

    return f"User {user.id}"


def _learner_names_for_tickets(
    tickets: list[EscalationTicket],
) -> dict[str, str]:
    """Resolve ticket user IDs in one database query.

    Ticket.user_id is stored as a string while User.id is an integer, so
    malformed/legacy ticket IDs are ignored instead of breaking the endpoint.
    """
    numeric_ids: set[int] = set()

    for ticket in tickets:
        if ticket.user_id is None:
            continue

        try:
            numeric_ids.add(int(str(ticket.user_id).strip()))
        except (TypeError, ValueError):
            logger.warning(
                "ticket_has_invalid_user_id",
                ticket_id=ticket.id,
                ticket_user_id=ticket.user_id,
            )

    if not numeric_ids:
        return {}

    with db_service.get_session_maker() as session:
        users = session.exec(
            select(User).where(User.id.in_(numeric_ids))
        ).all()

    return {
        str(user.id): _display_name(user)
        for user in users
    }


def _learner_name_for_ticket(ticket: EscalationTicket) -> str:
    """Resolve one ticket's learner name."""
    names = _learner_names_for_tickets([ticket])
    return names.get(str(ticket.user_id), "Unknown learner")


def _to_api_ticket(
    ticket: EscalationTicket,
    *,
    learner_name: str = "Unknown learner",
) -> OpsTicket:
    """Convert the persistence model into the public Ops API contract."""
    return OpsTicket(
        ticket_id=ticket.id,
        source=EscalationSource(ticket.source),
        reason=ticket.reason,
        status=TicketStatus(ticket.status),
        problem=ticket.problem,
        what_was_tried=ticket.what_was_tried,
        context=ticket.context,
        suggested_next_step=ticket.suggested_next_step,
        summary=ticket.summary,
        user_goal=ticket.user_goal,
        key_facts=list(ticket.key_facts),
        assistant_actions=list(ticket.assistant_actions),
        open_questions=list(ticket.open_questions),
        privacy_note=ticket.privacy_note,
        session_id=ticket.session_id,
        user_id=ticket.user_id,
        learner_name=learner_name,
        created_at=ticket.created_at,
    )


def _raise_http_error(
    exc: Exception,
    *,
    operation: str,
    ticket_id: str | None = None,
) -> NoReturn:
    """Translate service-layer failures without exposing internal details."""
    if isinstance(exc, TicketNotFoundError):
        logger.info(
            "ops_ticket_not_found",
            operation=operation,
            ticket_id=ticket_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    if isinstance(exc, TicketServiceError):
        logger.exception(
            "ops_ticket_service_failed",
            operation=operation,
            ticket_id=ticket_id,
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ticket service is temporarily unavailable",
        )

    logger.exception(
        "ops_ticket_api_failed",
        operation=operation,
        ticket_id=ticket_id,
        error_type=type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to complete the ticket operation",
    )


@router.get("", response_model=TicketListResponse)
@limiter.limit(_TICKET_RATE_LIMIT)
async def list_ops_tickets(
    request: Request,
    ticket_status: TicketStatus | None = Query(
        default=None,
        alias="status",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_ops_user),
) -> TicketListResponse:
    """List escalation tickets enriched with current learner names."""
    try:
        tickets = await list_tickets_from_service(
            status=ticket_status,
            offset=offset,
            limit=limit,
        )

        learner_names = _learner_names_for_tickets(tickets)

        api_tickets = [
            _to_api_ticket(
                ticket,
                learner_name=learner_names.get(
                    str(ticket.user_id),
                    "Unknown learner",
                ),
            )
            for ticket in tickets
        ]

        logger.info(
            "ops_tickets_listed",
            authenticated_user_id=current_user.id,
            status_filter=(
                ticket_status.value
                if ticket_status
                else None
            ),
            offset=offset,
            limit=limit,
            returned=len(api_tickets),
        )

        return TicketListResponse(
            tickets=api_tickets,
            offset=offset,
            limit=limit,
            returned=len(api_tickets),
        )

    except Exception as exc:
        _raise_http_error(exc, operation="list")


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
@limiter.limit(_TICKET_RATE_LIMIT)
async def view_ops_ticket(
    request: Request,
    ticket_id: str = Path(
        ...,
        min_length=5,
        max_length=80,
        pattern=r"^esc_[A-Za-z0-9_-]+$",
    ),
    current_user: User = Depends(get_current_ops_user),
) -> TicketDetailResponse:
    """Return one escalation ticket with learner identity."""
    try:
        ticket = await get_ticket_from_service(ticket_id)

        logger.info(
            "ops_ticket_viewed",
            ticket_id=ticket_id,
            authenticated_user_id=current_user.id,
        )

        return TicketDetailResponse(
            ticket=_to_api_ticket(
                ticket,
                learner_name=_learner_name_for_ticket(ticket),
            )
        )

    except Exception as exc:
        _raise_http_error(
            exc,
            operation="view",
            ticket_id=ticket_id,
        )


@router.patch(
    "/{ticket_id}/resolve",
    response_model=TicketDetailResponse,
)
@limiter.limit(_TICKET_RATE_LIMIT)
async def resolve_ops_ticket(
    request: Request,
    ticket_id: str = Path(
        ...,
        min_length=5,
        max_length=80,
        pattern=r"^esc_[A-Za-z0-9_-]+$",
    ),
    current_user: User = Depends(get_current_ops_user),
) -> TicketDetailResponse:
    """Resolve a ticket and return it with learner identity."""
    try:
        ticket = await resolve_ticket_from_service(ticket_id)

        logger.info(
            "ops_ticket_resolved",
            ticket_id=ticket_id,
            authenticated_user_id=current_user.id,
        )

        return TicketDetailResponse(
            ticket=_to_api_ticket(
                ticket,
                learner_name=_learner_name_for_ticket(ticket),
            )
        )

    except Exception as exc:
        _raise_http_error(
            exc,
            operation="resolve",
            ticket_id=ticket_id,
        )