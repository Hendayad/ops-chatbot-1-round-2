"""Validated contracts for internal Operations tickets.

The core handoff models already live in :mod:`app.schemas.escalation`. This
module reuses those models and adds the flattened response/update schemas needed
by the Week 3 ticket API. Keeping one source for ticket statuses and handoff
field limits prevents the API and escalation pipeline from drifting apart.
"""

from datetime import datetime
from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.base import BaseResponse
from app.schemas.escalation import (
    ConversationSummary,
    EscalationSource,
    EscalationTriggerRequest,
    EscalationTriggerResult,
    Ticket,
    TicketStatus,
)

TICKET_ID_PATTERN = r"^esc_[A-Za-z0-9_-]+$"
MAX_TICKET_PAGE_SIZE = 100

TicketId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=5,
        max_length=80,
        pattern=TICKET_ID_PATTERN,
    ),
]
OptionalTraceId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
SummaryItem = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]


class OpsTicket(BaseModel):
    """Privacy-scoped ticket returned by the internal Operations API.

    ``validation_alias`` allows this schema to validate the existing database
    model, whose primary key is named ``id``, while keeping the clearer public
    field name ``ticket_id``.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
    )

    ticket_id: TicketId = Field(
        validation_alias=AliasChoices("ticket_id", "id"),
        description="Internal escalation ticket identifier.",
    )
    source: EscalationSource = Field(description="Flow that created the ticket.")
    reason: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]
    status: TicketStatus
    problem: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=800),
    ]
    what_was_tried: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ]
    context: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1200),
    ]
    suggested_next_step: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=800),
    ]
    summary: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=800),
    ]
    user_goal: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=400),
    ]
    key_facts: list[SummaryItem] = Field(default_factory=list, max_length=8)
    assistant_actions: list[SummaryItem] = Field(default_factory=list, max_length=8)
    open_questions: list[SummaryItem] = Field(default_factory=list, max_length=5)
    privacy_note: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
    ]
    session_id: OptionalTraceId | None = None
    user_id: OptionalTraceId | None = None
    created_at: datetime


class TicketListResponse(BaseResponse):
    """One validated page of Operations tickets."""

    tickets: list[OpsTicket] = Field(default_factory=list)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=MAX_TICKET_PAGE_SIZE)
    returned: int = Field(default=0, ge=0)


class TicketDetailResponse(BaseResponse):
    """Response containing one Operations ticket."""

    ticket: OpsTicket


class TicketStatusUpdate(BaseModel):
    """Validated request body for changing one ticket's internal status."""

    model_config = ConfigDict(extra="forbid")

    status: TicketStatus


# ``TicketRead`` is a clearer service-layer name; ``OpsTicket`` is retained for
# compatibility with the existing Week 2 API terminology.
TicketRead = OpsTicket


__all__ = [
    "MAX_TICKET_PAGE_SIZE",
    "TICKET_ID_PATTERN",
    "ConversationSummary",
    "EscalationSource",
    "EscalationTriggerRequest",
    "EscalationTriggerResult",
    "OpsTicket",
    "Ticket",
    "TicketDetailResponse",
    "TicketId",
    "TicketListResponse",
    "TicketRead",
    "TicketStatus",
    "TicketStatusUpdate",
]