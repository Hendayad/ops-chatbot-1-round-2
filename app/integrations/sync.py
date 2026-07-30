"""Synchronize internal escalation tickets with an external ticket workspace.

The internal ticket store remains the source of truth. External connector
failures are recorded per ticket and never remove or hide the internal issue.
Until Operations selects a real workspace, this module uses the mock connector
from :mod:`app.integrations.ticketing`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol

from prometheus_client import Counter, Histogram
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.integrations.ticketing import (
    ExternalTicket,
    RetryingTicketingConnector,
    TicketingConnector,
    TicketingTemporaryError,
    TicketingTicketCreate,
    get_ticketing_connector,
)
from app.schemas.escalation import TicketStatus

logger = logging.getLogger(__name__)

_SYNC_RETRY_ATTEMPTS = 3
_DEFAULT_PAGE_SIZE = 100
_TERMINAL_STATUSES = frozenset({TicketStatus.RESOLVED, TicketStatus.CLOSED})


ticket_sync_events_total = Counter(
    "ticket_sync_events_total",
    "Ticket synchronization outcomes grouped by action and outcome.",
    ["action", "outcome"],
)

ticket_sync_duration_seconds = Histogram(
    "ticket_sync_duration_seconds",
    "Time spent synchronizing one internal ticket with the workspace.",
    buckets=[0.005, 0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0],
)


class InternalTicket(Protocol):
    """Minimum stored-ticket shape required by the synchronization service."""

    id: str
    source: str
    reason: str
    status: str
    problem: str
    what_was_tried: str
    context: str
    suggested_next_step: str
    summary: str
    created_at: datetime


class InternalTicketStore(Protocol):
    """Internal source-of-truth operations required by synchronization."""

    async def list_tickets(
        self,
        *,
        status: TicketStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[InternalTicket]:
        """List internal tickets."""
        ...

    async def get_ticket(self, ticket_id: str) -> InternalTicket:
        """Return one internal ticket."""
        ...

    async def resolve_ticket(self, ticket_id: str) -> InternalTicket:
        """Resolve one internal ticket idempotently."""
        ...


class TicketSyncAction(str, Enum):
    """Outcome of synchronizing one internal ticket."""

    CREATED_EXTERNAL = "created_external"
    PUSHED_STATUS = "pushed_status"
    PULLED_STATUS = "pulled_status"
    NO_CHANGE = "no_change"
    SKIPPED_TERMINAL = "skipped_terminal"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TicketSyncResult:
    """Result for one internal ticket synchronization attempt."""

    internal_ticket_id: str
    action: TicketSyncAction
    internal_status: TicketStatus
    external_ticket_id: str | None = None
    external_status: TicketStatus | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether this ticket synchronized without an error."""
        return self.action is not TicketSyncAction.FAILED


@dataclass(slots=True)
class TicketSyncReport:
    """Aggregate result returned by a complete synchronization pass."""

    results: list[TicketSyncResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Return the number of internal tickets inspected."""
        return len(self.results)

    @property
    def succeeded(self) -> int:
        """Return the number of successful or safely skipped tickets."""
        return sum(result.succeeded for result in self.results)

    @property
    def failed(self) -> int:
        """Return the number of connector or internal-update failures."""
        return self.total - self.succeeded

    def count(self, action: TicketSyncAction) -> int:
        """Count results having one synchronization action."""
        return sum(result.action is action for result in self.results)


class TicketSyncService:
    """Coordinate bidirectional status synchronization for escalation tickets."""

    def __init__(
        self,
        *,
        connector: TicketingConnector,
        ticket_service: InternalTicketStore,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> None:
        """Initialize the service with replaceable connector and store seams."""
        if not 1 <= page_size <= _DEFAULT_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {_DEFAULT_PAGE_SIZE}")

        self._connector = connector
        self._ticket_service = ticket_service
        self._page_size = page_size

    async def sync_all(self) -> TicketSyncReport:
        """Synchronize every internal ticket without stopping on one failure."""
        report = TicketSyncReport()
        offset = 0

        while True:
            tickets = await self._ticket_service.list_tickets(
                offset=offset,
                limit=self._page_size,
            )
            if not tickets:
                break

            for ticket in tickets:
                report.results.append(await self.sync_ticket(ticket))

            if len(tickets) < self._page_size:
                break
            offset += len(tickets)

        logger.info(
            "Ticket sync completed: total=%s succeeded=%s failed=%s created=%s pushed=%s pulled=%s",
            report.total,
            report.succeeded,
            report.failed,
            report.count(TicketSyncAction.CREATED_EXTERNAL),
            report.count(TicketSyncAction.PUSHED_STATUS),
            report.count(TicketSyncAction.PULLED_STATUS),
        )
        return report

    async def sync_ticket_by_id(self, ticket_id: str) -> TicketSyncResult:
        """Load and synchronize one internal ticket by ID."""
        ticket = await self._ticket_service.get_ticket(ticket_id)
        return await self.sync_ticket(ticket)

    async def sync_ticket(self, ticket: InternalTicket) -> TicketSyncResult:
        """Synchronize one ticket while preserving it on external failure."""
        internal_status = TicketStatus(ticket.status)

        try:
            with ticket_sync_duration_seconds.time():
                result = await self._sync_ticket(ticket, internal_status)
            ticket_sync_events_total.labels(action=result.action.value, outcome="success").inc()
            return result
        except Exception as exc:
            ticket_sync_events_total.labels(action=TicketSyncAction.FAILED.value, outcome="error").inc()
            logger.exception(
                "Ticket sync failed for %s with internal status %s",
                ticket.id,
                internal_status.value,
            )
            return TicketSyncResult(
                internal_ticket_id=ticket.id,
                action=TicketSyncAction.FAILED,
                internal_status=internal_status,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def list_internal_open_issues(self) -> list[InternalTicket]:
        """Return the resilient internal view when the workspace is unavailable."""
        open_tickets = await self._list_status(TicketStatus.OPEN)
        in_progress_tickets = await self._list_status(TicketStatus.IN_PROGRESS)
        return sorted(
            [*open_tickets, *in_progress_tickets],
            key=lambda ticket: ticket.created_at,
            reverse=True,
        )

    async def _sync_ticket(
        self,
        ticket: InternalTicket,
        internal_status: TicketStatus,
    ) -> TicketSyncResult:
        external = await self._find_external(ticket.id)

        if external is None:
            if internal_status in _TERMINAL_STATUSES:
                return TicketSyncResult(
                    internal_ticket_id=ticket.id,
                    action=TicketSyncAction.SKIPPED_TERMINAL,
                    internal_status=internal_status,
                )

            created = await self._create_external_ticket(
                self._build_create_payload(ticket, internal_status)
            )
            logger.info(
                "Created external ticket %s for internal ticket %s in %s",
                created.external_ticket_id,
                ticket.id,
                created.workspace,
            )
            return self._result(
                ticket=ticket,
                action=TicketSyncAction.CREATED_EXTERNAL,
                internal_status=internal_status,
                external=created,
            )

        external_status = TicketStatus(external.status)
        if self._statuses_equivalent(internal_status, external_status):
            return self._result(
                ticket=ticket,
                action=TicketSyncAction.NO_CHANGE,
                internal_status=internal_status,
                external=external,
            )

        if external_status in _TERMINAL_STATUSES and internal_status not in _TERMINAL_STATUSES:
            updated_internal = await self._ticket_service.resolve_ticket(ticket.id)
            pulled_status = TicketStatus(updated_internal.status)
            logger.info(
                "Pulled terminal status %s from external ticket %s into internal ticket %s",
                external_status.value,
                external.external_ticket_id,
                ticket.id,
            )
            return self._result(
                ticket=ticket,
                action=TicketSyncAction.PULLED_STATUS,
                internal_status=pulled_status,
                external=external,
            )

        updated_external = await self._push_external_status(
            external.external_ticket_id,
            internal_status,
        )
        logger.info(
            "Pushed internal status %s to external ticket %s",
            internal_status.value,
            external.external_ticket_id,
        )
        return self._result(
            ticket=ticket,
            action=TicketSyncAction.PUSHED_STATUS,
            internal_status=internal_status,
            external=updated_external,
        )

    async def _list_status(self, status: TicketStatus) -> list[InternalTicket]:
        tickets: list[InternalTicket] = []
        offset = 0

        while True:
            page = await self._ticket_service.list_tickets(
                status=status,
                offset=offset,
                limit=self._page_size,
            )
            tickets.extend(page)
            if len(page) < self._page_size:
                return tickets
            offset += len(page)

    @staticmethod
    def _build_create_payload(
        ticket: InternalTicket,
        status: TicketStatus,
    ) -> TicketingTicketCreate:
        """Build the privacy-scoped external issue payload."""
        source = ticket.source.strip() or "unknown"
        title = f"[{source}] {ticket.problem}"[:200]
        description = "\n\n".join(
            (
                f"Problem\n{ticket.problem}",
                f"What was tried\n{ticket.what_was_tried}",
                f"Context\n{ticket.context}",
                f"Summary\n{ticket.summary}",
                f"Suggested next step\n{ticket.suggested_next_step}",
            )
        )[:6000]
        return TicketingTicketCreate(
            internal_ticket_id=ticket.id,
            title=title,
            description=description,
            status=status,
            labels=["ops-escalation", source, status.value],
            metadata={"source": source, "reason": ticket.reason},
        )

    @staticmethod
    def _statuses_equivalent(left: TicketStatus, right: TicketStatus) -> bool:
        """Treat resolved and closed as equivalent terminal states."""
        return left is right or left in _TERMINAL_STATUSES and right in _TERMINAL_STATUSES

    @staticmethod
    def _result(
        *,
        ticket: InternalTicket,
        action: TicketSyncAction,
        internal_status: TicketStatus,
        external: ExternalTicket,
    ) -> TicketSyncResult:
        return TicketSyncResult(
            internal_ticket_id=ticket.id,
            action=action,
            internal_status=internal_status,
            external_ticket_id=external.external_ticket_id,
            external_status=TicketStatus(external.status),
        )

    async def _find_external(self, internal_ticket_id: str) -> ExternalTicket | None:
        """Find an external ticket without stacking two retry wrappers."""
        if isinstance(self._connector, RetryingTicketingConnector):
            return await self._connector.get_ticket_by_internal_id(internal_ticket_id)
        return await self._get_external_by_internal_id(internal_ticket_id)

    async def _create_external_ticket(self, payload: TicketingTicketCreate) -> ExternalTicket:
        """Create an external ticket without stacking two retry wrappers."""
        if isinstance(self._connector, RetryingTicketingConnector):
            return await self._connector.create_ticket(payload)
        return await self._create_external(payload)

    async def _push_external_status(
        self,
        external_ticket_id: str,
        status: TicketStatus,
    ) -> ExternalTicket:
        """Update external status without stacking two retry wrappers."""
        if isinstance(self._connector, RetryingTicketingConnector):
            return await self._connector.update_ticket_status(external_ticket_id, status)
        return await self._update_external_status(external_ticket_id, status)

    @retry(
        retry=retry_if_exception_type(TicketingTemporaryError),
        stop=stop_after_attempt(_SYNC_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
        reraise=True,
    )
    async def _get_external_by_internal_id(self, internal_ticket_id: str) -> ExternalTicket | None:
        """Read the external mirror, retrying temporary failures."""
        return await self._connector.get_ticket_by_internal_id(internal_ticket_id)

    @retry(
        retry=retry_if_exception_type(TicketingTemporaryError),
        stop=stop_after_attempt(_SYNC_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
        reraise=True,
    )
    async def _create_external(self, payload: TicketingTicketCreate) -> ExternalTicket:
        """Create the external mirror, retrying temporary failures."""
        return await self._connector.create_ticket(payload)

    @retry(
        retry=retry_if_exception_type(TicketingTemporaryError),
        stop=stop_after_attempt(_SYNC_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
        reraise=True,
    )
    async def _update_external_status(
        self,
        external_ticket_id: str,
        status: TicketStatus,
    ) -> ExternalTicket:
        """Push an internal status, retrying temporary failures."""
        return await self._connector.update_ticket_status(external_ticket_id, status)


_default_sync_service: TicketSyncService | None = None


def get_ticket_sync_service() -> TicketSyncService:
    """Create the default service lazily to keep imports and tests lightweight."""
    global _default_sync_service
    if _default_sync_service is None:
        from app.tickets.service import TicketService

        _default_sync_service = TicketSyncService(
            connector=get_ticketing_connector(),
            ticket_service=TicketService(),
        )
    return _default_sync_service


async def sync_tickets() -> TicketSyncReport:
    """Run one complete synchronization pass with default dependencies."""
    return await get_ticket_sync_service().sync_all()


async def sync_ticket(ticket_id: str) -> TicketSyncResult:
    """Synchronize one internal ticket using default dependencies."""
    return await get_ticket_sync_service().sync_ticket_by_id(ticket_id)


async def list_internal_open_issues() -> list[InternalTicket]:
    """Return internal unresolved issues without depending on the workspace."""
    return await get_ticket_sync_service().list_internal_open_issues()


__all__ = [
    "InternalTicket",
    "InternalTicketStore",
    "TicketSyncAction",
    "TicketSyncReport",
    "TicketSyncResult",
    "TicketSyncService",
    "get_ticket_sync_service",
    "list_internal_open_issues",
    "sync_ticket",
    "sync_tickets",
]
