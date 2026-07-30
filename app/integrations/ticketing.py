"""External ticketing connector contracts and a safe local adapter.

The internal escalation-ticket table remains the source of truth. This module
only defines the boundary used to mirror privacy-scoped unresolved issues into
an external Operations workspace. Because the project has not selected a real
workspace yet, the default implementation is an idempotent in-memory adapter
for development and tests.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from prometheus_client import Counter, Histogram
from pydantic import BaseModel, ConfigDict, Field
from tenacity import AsyncRetrying, RetryCallState, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import logger
from app.models.escalation_ticket import EscalationTicket
from app.schemas.escalation import TicketStatus

_DEFAULT_RETRY_ATTEMPTS = 3
_MAX_TITLE_LENGTH = 160
_MAX_DESCRIPTION_LENGTH = 5_000
_MAX_METADATA_VALUE_LENGTH = 500

T = TypeVar("T")


ticketing_connector_operations_total = Counter(
    "ticketing_connector_operations_total",
    "External ticketing connector operations grouped by workspace, operation, and outcome.",
    ["workspace", "operation", "outcome"],
)

ticketing_connector_duration_seconds = Histogram(
    "ticketing_connector_duration_seconds",
    "Time spent performing external ticketing connector operations.",
    ["workspace", "operation"],
    buckets=[0.005, 0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0],
)


class TicketingConnectorError(RuntimeError):
    """Base exception for external ticketing connector failures."""


class TicketingConfigurationError(TicketingConnectorError):
    """Raised when the requested ticketing workspace is not configured."""


class TicketingTemporaryError(TicketingConnectorError):
    """Raised for retryable external workspace failures."""


class ExternalTicketNotFoundError(TicketingConnectorError):
    """Raised when an external ticket cannot be found."""

    def __init__(self, ticket_id: str) -> None:
        """Initialize the exception with the missing external ticket ID."""
        super().__init__(f"External ticket {ticket_id!r} was not found.")
        self.ticket_id = ticket_id


class TicketingTicketCreate(BaseModel):
    """Privacy-scoped payload sent to an external ticketing workspace."""

    model_config = ConfigDict(extra="forbid")

    internal_ticket_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=_MAX_TITLE_LENGTH)
    description: str = Field(min_length=1, max_length=_MAX_DESCRIPTION_LENGTH)
    status: TicketStatus = TicketStatus.OPEN
    labels: list[str] = Field(default_factory=list, max_length=10)
    metadata: dict[str, str] = Field(default_factory=dict)


class ExternalTicket(BaseModel):
    """Normalized ticket representation returned by any workspace adapter."""

    model_config = ConfigDict(extra="forbid")

    workspace: str = Field(min_length=1, max_length=60)
    external_ticket_id: str = Field(min_length=1, max_length=120)
    internal_ticket_id: str = Field(min_length=1, max_length=80)
    status: TicketStatus
    url: str | None = Field(default=None, max_length=2_000)
    updated_at: datetime


class TicketingConnector(Protocol):
    """Contract that a Jira, Linear, ClickUp, or other adapter must implement."""

    @property
    def workspace_name(self) -> str:
        """Return the connector's stable workspace name."""
        ...

    async def create_ticket(self, payload: TicketingTicketCreate) -> ExternalTicket:
        """Create a ticket idempotently using ``internal_ticket_id`` as the key."""
        ...

    async def get_ticket(self, external_ticket_id: str) -> ExternalTicket:
        """Return one external ticket by its workspace ID."""
        ...

    async def get_ticket_by_internal_id(self, internal_ticket_id: str) -> ExternalTicket | None:
        """Find a mirrored external ticket using the internal source-of-truth ID."""
        ...

    async def update_ticket_status(
        self,
        external_ticket_id: str,
        status: TicketStatus,
    ) -> ExternalTicket:
        """Update an external ticket status and return the normalized result."""
        ...


class InMemoryTicketingConnector:
    """Deterministic local connector used until a real workspace is selected.

    The adapter is concurrency-safe and idempotent. Repeating ``create_ticket``
    with the same internal ticket ID returns the existing external ticket rather
    than creating a duplicate.
    """

    def __init__(self, workspace_name: str = "memory") -> None:
        """Initialize an empty in-memory workspace."""
        normalized_name = workspace_name.strip().lower()
        if not normalized_name:
            raise ValueError("workspace_name must not be blank")

        self._workspace_name = normalized_name
        self._tickets: dict[str, ExternalTicket] = {}
        self._external_id_by_internal_id: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._next_id = 1

    @property
    def workspace_name(self) -> str:
        """Return the local workspace name."""
        return self._workspace_name

    async def create_ticket(self, payload: TicketingTicketCreate) -> ExternalTicket:
        """Create or return the existing mirror for an internal ticket."""
        async with self._lock:
            existing_id = self._external_id_by_internal_id.get(payload.internal_ticket_id)
            if existing_id is not None:
                return self._tickets[existing_id].model_copy(deep=True)

            external_id = f"{self._workspace_name}_{self._next_id:06d}"
            self._next_id += 1
            ticket = ExternalTicket(
                workspace=self._workspace_name,
                external_ticket_id=external_id,
                internal_ticket_id=payload.internal_ticket_id,
                status=payload.status,
                updated_at=datetime.now(UTC),
            )
            self._tickets[external_id] = ticket
            self._external_id_by_internal_id[payload.internal_ticket_id] = external_id
            return ticket.model_copy(deep=True)

    async def get_ticket(self, external_ticket_id: str) -> ExternalTicket:
        """Return a copy of one stored external ticket."""
        normalized_id = _required_text(external_ticket_id, field_name="external_ticket_id")
        async with self._lock:
            ticket = self._tickets.get(normalized_id)
            if ticket is None:
                raise ExternalTicketNotFoundError(normalized_id)
            return ticket.model_copy(deep=True)

    async def get_ticket_by_internal_id(self, internal_ticket_id: str) -> ExternalTicket | None:
        """Return the mirrored ticket for an internal ticket, when present."""
        normalized_id = _required_text(internal_ticket_id, field_name="internal_ticket_id")
        async with self._lock:
            external_id = self._external_id_by_internal_id.get(normalized_id)
            if external_id is None:
                return None
            return self._tickets[external_id].model_copy(deep=True)

    async def update_ticket_status(
        self,
        external_ticket_id: str,
        status: TicketStatus,
    ) -> ExternalTicket:
        """Update a stored external ticket status idempotently."""
        normalized_id = _required_text(external_ticket_id, field_name="external_ticket_id")
        normalized_status = TicketStatus(status)

        async with self._lock:
            current = self._tickets.get(normalized_id)
            if current is None:
                raise ExternalTicketNotFoundError(normalized_id)
            if current.status == normalized_status:
                return current.model_copy(deep=True)

            updated = current.model_copy(
                update={
                    "status": normalized_status,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._tickets[normalized_id] = updated
            return updated.model_copy(deep=True)


class RetryingTicketingConnector:
    """Apply bounded exponential-backoff retries around another connector.

    Only ``TicketingTemporaryError`` is retried. Configuration, validation, and
    not-found errors fail immediately because repeating those operations would
    not fix them.
    """

    def __init__(
        self,
        connector: TicketingConnector,
        *,
        attempts: int = _DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        """Wrap a connector with retry, metrics, and structured logging."""
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self._connector = connector
        self._attempts = attempts

    @property
    def workspace_name(self) -> str:
        """Return the wrapped connector's workspace name."""
        return self._connector.workspace_name

    async def create_ticket(self, payload: TicketingTicketCreate) -> ExternalTicket:
        """Create a ticket with bounded retries for temporary failures."""
        return await self._execute("create", lambda: self._connector.create_ticket(payload))

    async def get_ticket(self, external_ticket_id: str) -> ExternalTicket:
        """Fetch an external ticket with bounded retries."""
        return await self._execute("get", lambda: self._connector.get_ticket(external_ticket_id))

    async def get_ticket_by_internal_id(self, internal_ticket_id: str) -> ExternalTicket | None:
        """Find an external ticket by internal ID with bounded retries."""
        return await self._execute(
            "find_by_internal_id",
            lambda: self._connector.get_ticket_by_internal_id(internal_ticket_id),
        )

    async def update_ticket_status(
        self,
        external_ticket_id: str,
        status: TicketStatus,
    ) -> ExternalTicket:
        """Update an external status with bounded retries."""
        return await self._execute(
            "update_status",
            lambda: self._connector.update_ticket_status(external_ticket_id, status),
        )

    async def _execute(self, operation: str, callback: Callable[[], Awaitable[T]]) -> T:
        """Execute one connector operation and record its final outcome."""
        workspace = self.workspace_name
        try:
            with ticketing_connector_duration_seconds.labels(
                workspace=workspace,
                operation=operation,
            ).time():
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(self._attempts),
                    wait=wait_exponential(multiplier=0.25, min=0.25, max=2.0),
                    retry=retry_if_exception_type(TicketingTemporaryError),
                    before_sleep=self._log_retry,
                    reraise=True,
                ):
                    with attempt:
                        result = await callback()
                        ticketing_connector_operations_total.labels(
                            workspace=workspace,
                            operation=operation,
                            outcome="success",
                        ).inc()
                        return result
        except Exception:
            ticketing_connector_operations_total.labels(
                workspace=workspace,
                operation=operation,
                outcome="error",
            ).inc()
            logger.exception(
                "ticketing_connector_operation_failed",
                workspace=workspace,
                operation=operation,
            )
            raise

        raise RuntimeError("Ticketing retry loop ended without a result")

    def _log_retry(self, retry_state: RetryCallState) -> None:
        """Log one temporary connector failure before the next attempt."""
        exception = retry_state.outcome.exception() if retry_state.outcome is not None else None
        logger.warning(
            "ticketing_connector_retrying",
            workspace=self.workspace_name,
            attempt=retry_state.attempt_number,
            error_type=type(exception).__name__ if exception is not None else "unknown",
        )


def build_ticket_payload(ticket: EscalationTicket) -> TicketingTicketCreate:
    """Convert an internal escalation ticket into a privacy-scoped payload.

    The payload deliberately excludes the raw chat transcript, ``user_id``, and
    ``session_id``. The external workspace receives only the structured handoff
    needed by Operations, while the complete internal record remains authoritative.
    """
    problem = _required_text(ticket.problem, field_name="problem")
    source = _required_text(ticket.source, field_name="source")
    reason = _required_text(ticket.reason, field_name="reason")
    status = TicketStatus(ticket.status)

    title = _truncate(f"[Ops] {problem}", _MAX_TITLE_LENGTH)
    description = _truncate(
        "\n\n".join(
            (
                f"## Problem\n{problem}",
                f"## What was tried\n{_required_text(ticket.what_was_tried, field_name='what_was_tried')}",
                f"## Context\n{_required_text(ticket.context, field_name='context')}",
                (
                    "## Suggested next step\n"
                    f"{_required_text(ticket.suggested_next_step, field_name='suggested_next_step')}"
                ),
                f"## Summary\n{_required_text(ticket.summary, field_name='summary')}",
                f"## Internal ticket\n{ticket.id}",
            )
        ),
        _MAX_DESCRIPTION_LENGTH,
    )

    return TicketingTicketCreate(
        internal_ticket_id=_required_text(ticket.id, field_name="id"),
        title=title,
        description=description,
        status=status,
        labels=["ops-escalation", f"source:{_slug(source)}"],
        metadata={
            "source": _truncate(source, _MAX_METADATA_VALUE_LENGTH),
            "reason": _truncate(reason, _MAX_METADATA_VALUE_LENGTH),
        },
    )


def create_ticketing_connector(workspace: str | None = None) -> TicketingConnector:
    """Create a configured connector.

    ``memory`` and ``mock`` are intentionally the only supported values until
    Operations chooses a real workspace and provides its API contract and
    credentials. Unknown providers fail loudly instead of pretending that a
    ticket was synchronized.
    """
    selected = (workspace or os.getenv("TICKETING_WORKSPACE", "memory")).strip().lower()
    if selected in {"memory", "mock", "in-memory", "in_memory"}:
        return RetryingTicketingConnector(InMemoryTicketingConnector("memory"))

    raise TicketingConfigurationError(
        f"Unsupported ticketing workspace {selected!r}. "
        "Configure 'memory' for local development or implement the selected provider adapter."
    )


_default_ticketing_connector: TicketingConnector | None = None


def get_ticketing_connector() -> TicketingConnector:
    """Return the process-wide connector used by the synchronization service."""
    global _default_ticketing_connector
    if _default_ticketing_connector is None:
        _default_ticketing_connector = create_ticketing_connector()
    return _default_ticketing_connector


def _required_text(value: object, *, field_name: str) -> str:
    """Normalize a required text value or raise a clear validation error."""
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _truncate(value: str, limit: int) -> str:
    """Truncate text without exceeding the destination field limit."""
    normalized = value.strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _slug(value: str) -> str:
    """Create a short label-safe slug."""
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return _truncate(normalized or "unknown", 40)


__all__ = [
    "ExternalTicket",
    "ExternalTicketNotFoundError",
    "InMemoryTicketingConnector",
    "RetryingTicketingConnector",
    "TicketingConfigurationError",
    "TicketingConnector",
    "TicketingConnectorError",
    "TicketingTemporaryError",
    "TicketingTicketCreate",
    "build_ticket_payload",
    "create_ticketing_connector",
    "get_ticketing_connector",
]