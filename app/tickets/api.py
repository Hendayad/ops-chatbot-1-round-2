"""Public Operations ticket API for the Week 3 ticket package.

The working FastAPI implementation already lives in ``app.api.v1.tickets`` and
is registered by the versioned API router. This module re-exports that single
implementation so Week 3 code can import from ``app.tickets.api`` without
copying endpoints, response models, authentication, or rate-limit logic.
"""

from app.api.v1.tickets import (
    OpsTicket,
    TicketDetailResponse,
    TicketListResponse,
    list_ops_tickets,
    resolve_ops_ticket,
    router,
    view_ops_ticket,
)

__all__ = [
    "OpsTicket",
    "TicketDetailResponse",
    "TicketListResponse",
    "list_ops_tickets",
    "resolve_ops_ticket",
    "router",
    "view_ops_ticket",
]