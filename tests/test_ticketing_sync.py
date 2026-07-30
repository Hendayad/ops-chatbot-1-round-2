"""Tests for the Week 3 mock ticketing connector and status synchronization."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from app.integrations.sync import TicketSyncAction, TicketSyncService
from app.integrations.ticketing import (
    ExternalTicket,
    InMemoryTicketingConnector,
    TicketingConnector,
    TicketingTemporaryError,
    TicketingTicketCreate,
    create_ticketing_connector,
)
from app.schemas.escalation import TicketStatus

T = TypeVar("T")


def _run(coroutine: Coroutine[Any, Any, T]) -> T:
    """Run one async connector or sync-service operation."""
    return asyncio.run(coroutine)


@dataclass(slots=True)
class FakeTicket:
    """Small internal-ticket object used instead of a real database record."""

    id: str
    source: str = "answering"
    reason: str = "The approved materials did not contain an answer."
    status: str = TicketStatus.OPEN.value
    problem: str = "The learner cannot verify the submission deadline."
    what_was_tried: str = "The assistant searched the approved materials."
    context: str = "No grounded answer was available."
    suggested_next_step: str = "Operations should confirm the deadline."
    summary: str = "The learner needs a verified deadline."
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _ticket(
    ticket_id: str = "esc_123",
    *,
    status: TicketStatus = TicketStatus.OPEN,
    created_at: datetime | None = None,
) -> FakeTicket:
    """Build a valid internal ticket for synchronization tests."""
    ticket = FakeTicket(id=ticket_id, status=status.value)
    if created_at is not None:
        ticket.created_at = created_at
    return ticket


class FakeTicketService:
    """In-memory substitute for the internal ticket service."""

    def __init__(self, tickets: Sequence[FakeTicket]) -> None:
        self.tickets = {ticket.id: ticket for ticket in tickets}
        self.resolve_calls: list[str] = []

    async def list_tickets(
        self,
        *,
        status: TicketStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[FakeTicket]:
        """Return one filtered and paginated internal-ticket page."""
        values = list(self.tickets.values())
        if status is not None:
            values = [ticket for ticket in values if ticket.status == status.value]
        return values[offset : offset + limit]

    async def get_ticket(self, ticket_id: str) -> FakeTicket:
        """Return one stored fake ticket."""
        return self.tickets[ticket_id]

    async def resolve_ticket(self, ticket_id: str) -> FakeTicket:
        """Resolve one stored fake ticket and record the call."""
        self.resolve_calls.append(ticket_id)
        ticket = self.tickets[ticket_id]
        ticket.status = TicketStatus.RESOLVED.value
        return ticket


class FlakyConnector(InMemoryTicketingConnector):
    """Connector that temporarily fails its external-ticket lookup."""

    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures
        self.lookup_attempts = 0

    async def get_ticket_by_internal_id(self, internal_ticket_id: str) -> ExternalTicket | None:
        """Fail a configured number of times, then use the mock connector."""
        self.lookup_attempts += 1
        if self.lookup_attempts <= self.failures:
            raise TicketingTemporaryError("temporary outage")
        return await super().get_ticket_by_internal_id(internal_ticket_id)


class BrokenConnector(InMemoryTicketingConnector):
    """Connector that represents a permanently unavailable workspace."""

    async def get_ticket_by_internal_id(self, internal_ticket_id: str) -> ExternalTicket | None:
        """Always fail instead of returning an external ticket."""
        raise RuntimeError("workspace unavailable")


def _service(
    tickets: Sequence[FakeTicket],
    connector: TicketingConnector | None = None,
    *,
    page_size: int = 2,
) -> TicketSyncService:
    """Build the synchronization service with deterministic fake dependencies."""
    return TicketSyncService(
        connector=connector or InMemoryTicketingConnector(),
        ticket_service=FakeTicketService(tickets),
        page_size=page_size,
    )


def test_mock_workspace_factory_returns_working_in_memory_connector() -> None:
    """The unchanged mock configuration should remain usable locally."""
    connector = create_ticketing_connector("mock")
    payload = TicketingTicketCreate(
        internal_ticket_id="esc_factory",
        title="Deadline issue",
        description="Operations should confirm the official deadline.",
    )

    external = _run(connector.create_ticket(payload))

    assert connector.workspace_name == "memory"
    assert external.internal_ticket_id == "esc_factory"
    assert external.status is TicketStatus.OPEN


def test_in_memory_connector_is_idempotent() -> None:
    """Creating the same internal ticket twice must not create duplicates."""
    connector = InMemoryTicketingConnector()
    payload = TicketingTicketCreate(
        internal_ticket_id="esc_idempotent",
        title="Issue",
        description="Description",
    )

    first = _run(connector.create_ticket(payload))
    second = _run(connector.create_ticket(payload))

    assert first.external_ticket_id == second.external_ticket_id


def test_sync_creates_external_ticket_for_open_internal_ticket() -> None:
    """An unresolved internal ticket should be mirrored to the mock workspace."""
    ticket = _ticket()
    connector = InMemoryTicketingConnector()
    service = _service([ticket], connector)

    result = _run(service.sync_ticket(ticket))
    external = _run(connector.get_ticket_by_internal_id(ticket.id))

    assert result.action is TicketSyncAction.CREATED_EXTERNAL
    assert external is not None
    assert external.internal_ticket_id == ticket.id
    assert external.status is TicketStatus.OPEN


def test_sync_is_idempotent_after_external_ticket_exists() -> None:
    """A second sync pass should reuse the existing external mirror."""
    ticket = _ticket()
    connector = InMemoryTicketingConnector()
    service = _service([ticket], connector)

    first = _run(service.sync_ticket(ticket))
    second = _run(service.sync_ticket(ticket))

    assert first.action is TicketSyncAction.CREATED_EXTERNAL
    assert second.action is TicketSyncAction.NO_CHANGE
    assert first.external_ticket_id == second.external_ticket_id


def test_external_resolution_is_pulled_to_internal_ticket() -> None:
    """A terminal external status should resolve the internal source of truth."""
    ticket = _ticket()
    connector = InMemoryTicketingConnector()
    ticket_service = FakeTicketService([ticket])
    service = TicketSyncService(connector=connector, ticket_service=ticket_service)
    external = _run(
        connector.create_ticket(
            TicketingTicketCreate(
                internal_ticket_id=ticket.id,
                title="Issue",
                description="Description",
            )
        )
    )
    _run(connector.update_ticket_status(external.external_ticket_id, TicketStatus.RESOLVED))

    result = _run(service.sync_ticket(ticket))

    assert result.action is TicketSyncAction.PULLED_STATUS
    assert result.internal_status is TicketStatus.RESOLVED
    assert ticket_service.resolve_calls == [ticket.id]


def test_internal_resolution_is_pushed_to_external_ticket() -> None:
    """A later internal resolution should update the existing external mirror."""
    ticket = _ticket()
    connector = InMemoryTicketingConnector()
    service = _service([ticket], connector)
    created = _run(service.sync_ticket(ticket))
    ticket.status = TicketStatus.RESOLVED.value

    result = _run(service.sync_ticket(ticket))

    assert created.external_ticket_id is not None
    external = _run(connector.get_ticket(created.external_ticket_id))
    assert result.action is TicketSyncAction.PUSHED_STATUS
    assert external.status is TicketStatus.RESOLVED


def test_terminal_ticket_without_external_mirror_is_skipped() -> None:
    """A resolved internal ticket should not create a new external issue."""
    ticket = _ticket(status=TicketStatus.RESOLVED)
    connector = InMemoryTicketingConnector()
    service = _service([ticket], connector)

    result = _run(service.sync_ticket(ticket))
    external = _run(connector.get_ticket_by_internal_id(ticket.id))

    assert result.action is TicketSyncAction.SKIPPED_TERMINAL
    assert external is None


def test_temporary_connector_failure_is_retried() -> None:
    """Temporary connector failures should use the configured retry backoff."""
    ticket = _ticket()
    connector = FlakyConnector(failures=2)
    service = _service([ticket], connector)

    result = _run(service.sync_ticket(ticket))

    assert result.action is TicketSyncAction.CREATED_EXTERNAL
    assert connector.lookup_attempts == 3


def test_connector_failure_keeps_internal_ticket_available() -> None:
    """A workspace failure must not hide the internal source-of-truth issue."""
    ticket = _ticket()
    service = _service([ticket], BrokenConnector())

    result = _run(service.sync_ticket(ticket))
    open_issues = _run(service.list_internal_open_issues())

    assert result.action is TicketSyncAction.FAILED
    assert result.error is not None
    assert [issue.id for issue in open_issues] == [ticket.id]


def test_internal_open_issues_excludes_terminal_tickets_and_sorts_newest_first() -> None:
    """The fallback view should show only unresolved issues in useful order."""
    now = datetime.now(UTC)
    old_open = _ticket("esc_old", created_at=now - timedelta(hours=2))
    new_in_progress = _ticket(
        "esc_new",
        status=TicketStatus.IN_PROGRESS,
        created_at=now,
    )
    resolved = _ticket(
        "esc_done",
        status=TicketStatus.RESOLVED,
        created_at=now + timedelta(hours=1),
    )
    service = _service([old_open, new_in_progress, resolved])

    open_issues = _run(service.list_internal_open_issues())

    assert [issue.id for issue in open_issues] == ["esc_new", "esc_old"]


def test_sync_all_continues_after_one_ticket_fails() -> None:
    """One connector error should not stop synchronization of later tickets."""
    first = _ticket("esc_first")
    second = _ticket("esc_second")

    class SelectiveConnector(InMemoryTicketingConnector):
        async def get_ticket_by_internal_id(self, internal_ticket_id: str) -> ExternalTicket | None:
            if internal_ticket_id == first.id:
                raise RuntimeError("first ticket failed")
            return await super().get_ticket_by_internal_id(internal_ticket_id)

    service = _service([first, second], SelectiveConnector())

    report = _run(service.sync_all())

    assert report.total == 2
    assert report.failed == 1
    assert report.succeeded == 1
    assert report.count(TicketSyncAction.CREATED_EXTERNAL) == 1