"""Tests for escalation ticket schemas and scaffold trigger."""

import asyncio
import importlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from app.schemas.escalation import (
    ConversationSummary,
    EscalationSource,
    EscalationTriggerRequest,
    EscalationTriggerResult,
    Ticket,
    TicketStatus,
)
from app.api.v1 import tickets as v1_tickets_api
from app.escalation.detector import (
    EscalationTrigger,
    detect_escalation,
)
from app.services import escalation as escalation_service
from app.services.escalation import DatabaseEscalationTrigger, NoopEscalationTrigger
from app.tickets import api as week3_ticket_api
from app.tickets import schema as ticket_schema

escalate_to_human_module = importlib.import_module("app.core.langgraph.tools.escalate_to_human")
escalate_to_human = escalate_to_human_module.escalate_to_human


def build_valid_ticket() -> Ticket:
    """Build a valid ticket for schema and service tests."""
    return Ticket(
        problem="Learner cannot find the assignment deadline.",
        what_was_tried="The assistant checked approved materials but did not find a grounded answer.",
        context="The learner asked about the current sprint assignment deadline.",
        suggested_next_step="Operations should confirm the deadline and update the approved materials if needed.",
        status=TicketStatus.OPEN,
    )


def build_valid_summary() -> ConversationSummary:
    """Build a privacy-preserving conversation summary."""
    return ConversationSummary(
        summary="Learner needs clarification on an assignment deadline.",
        user_goal="Know when the assignment is due.",
        key_facts=[
            "The answer was not found in approved materials.",
            "The assistant avoided giving an unsupported answer.",
        ],
        assistant_actions=[
            "Searched available approved context.",
            "Prepared an escalation handoff.",
        ],
        open_questions=[
            "What is the official assignment deadline?",
        ],
    )


def test_ticket_accepts_python_field_names_and_exports_kebab_case_aliases():
    ticket = build_valid_ticket()

    payload = ticket.model_dump(by_alias=True)

    assert payload["problem"] == "Learner cannot find the assignment deadline."
    assert payload["what-was-tried"].startswith("The assistant checked approved materials")
    assert payload["suggested-next-step"].startswith("Operations should confirm")
    assert payload["status"] == "open"


def test_ticket_accepts_shared_json_contract_aliases():
    ticket = Ticket.model_validate(
        {
            "problem": "Learner cannot access onboarding materials.",
            "what-was-tried": "The assistant checked approved FAQs and onboarding notes.",
            "context": "The learner says the onboarding link is unavailable.",
            "suggested-next-step": "Operations should verify the onboarding link and send the correct one.",
            "status": "open",
        }
    )

    assert ticket.what_was_tried.startswith("The assistant checked")
    assert ticket.suggested_next_step.startswith("Operations should")
    assert ticket.status == TicketStatus.OPEN


def test_ticket_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Ticket.model_validate(
            {
                "problem": "Learner has a schedule question.",
                "what-was-tried": "Assistant searched approved materials.",
                "context": "Question is about session timing.",
                "suggested-next-step": "Ops should confirm the schedule.",
                "status": "open",
                "raw_transcript": "This should not be accepted.",
            }
        )


def test_ticket_rejects_too_long_problem():
    with pytest.raises(ValidationError):
        Ticket(
            problem="x" * 801,
            what_was_tried="Assistant searched approved materials.",
            context="Question is about session timing.",
            suggested_next_step="Ops should confirm the schedule.",
        )


def test_conversation_summary_rejects_raw_transcript_field():
    with pytest.raises(ValidationError):
        ConversationSummary.model_validate(
            {
                "summary": "Learner needs support.",
                "user_goal": "Get a reliable answer.",
                "key_facts": ["No grounded answer was found."],
                "assistant_actions": ["Assistant prepared an escalation."],
                "open_questions": ["What should Ops tell the learner?"],
                "raw_transcript": "Full chat history should not be part of the summary contract.",
            }
        )


def test_escalation_trigger_request_shape():
    request = EscalationTriggerRequest(
        source=EscalationSource.ANSWERING,
        reason="No grounded answer found in approved Operations materials.",
        ticket=build_valid_ticket(),
        conversation_summary=build_valid_summary(),
        session_id="session_123",
        user_id="user_456",
    )

    assert request.source == EscalationSource.ANSWERING
    assert request.ticket.status == TicketStatus.OPEN
    assert request.conversation_summary.summary.startswith("Learner needs clarification")


def test_noop_escalation_trigger_returns_stable_result():
    request = EscalationTriggerRequest(
        source=EscalationSource.ANSWERING,
        reason="No grounded answer found in approved Operations materials.",
        ticket=build_valid_ticket(),
        conversation_summary=build_valid_summary(),
        session_id="session_123",
        user_id="user_456",
    )

    result = asyncio.run(NoopEscalationTrigger().trigger(request))

    assert result.triggered is True
    assert result.status == request.ticket.status
    assert result.ticket_id is None
    assert "No external ticket was created" in result.message


def test_database_escalation_trigger_returns_persisted_ticket_id(monkeypatch: pytest.MonkeyPatch):
    request = EscalationTriggerRequest(
        source=EscalationSource.ANSWERING,
        reason="No grounded answer found in approved Operations materials.",
        ticket=build_valid_ticket(),
        conversation_summary=build_valid_summary(),
        session_id="session_123",
        user_id="user_456",
    )

    class FakeDatabaseService:
        async def create_escalation_ticket(self, **kwargs):
            assert kwargs["source"] == "answering"
            assert kwargs["session_id"] == "session_123"
            assert kwargs["user_id"] == "user_456"

            class TicketRecord:
                id = "esc_123abc"

            return TicketRecord()

    import sys
    import types

    fake_module = types.ModuleType("app.services.database")
    fake_module.database_service = FakeDatabaseService()
    monkeypatch.setitem(sys.modules, "app.services.database", fake_module)

    result = asyncio.run(DatabaseEscalationTrigger().trigger(request))

    assert result.triggered is True
    assert result.ticket_id == "esc_123abc"
    assert result.status == TicketStatus.OPEN
    assert "esc_123abc" in result.message


def test_trigger_answering_escalation_builds_valid_request(monkeypatch: pytest.MonkeyPatch):
    captured_request = None

    async def fake_trigger(request: EscalationTriggerRequest) -> EscalationTriggerResult:
        nonlocal captured_request
        captured_request = request
        return EscalationTriggerResult(triggered=True, status=request.ticket.status, ticket_id="esc_123")

    monkeypatch.setattr(
        escalation_service, "escalation_trigger", AsyncMock(trigger=AsyncMock(side_effect=fake_trigger))
    )

    result = asyncio.run(
        escalation_service.trigger_answering_escalation(
            reason="No grounded answer found in approved Operations materials.",
            problem="Learner cannot find the assignment deadline.",
            what_was_tried="Assistant searched approved materials.",
            context="The learner asked about the current sprint assignment deadline.",
            suggested_next_step="Operations should confirm the deadline.",
            summary="Learner needs clarification on an assignment deadline.",
            user_goal="Know when the assignment is due.",
            key_facts=["No grounded deadline was found."],
            assistant_actions=["Searched approved materials."],
            open_questions=["What is the official assignment deadline?"],
            session_id="session_123",
            user_id="user_456",
        )
    )

    assert result.triggered is True
    assert result.ticket_id == "esc_123"
    assert captured_request is not None
    assert captured_request.source == EscalationSource.ANSWERING
    assert captured_request.session_id == "session_123"
    assert captured_request.user_id == "user_456"
    assert captured_request.ticket.problem == "Learner cannot find the assignment deadline."


def test_trigger_proactive_escalation_uses_proactive_source(monkeypatch: pytest.MonkeyPatch):
    captured_request = None

    async def fake_trigger(request: EscalationTriggerRequest) -> EscalationTriggerResult:
        nonlocal captured_request
        captured_request = request
        return EscalationTriggerResult(triggered=True, status=request.ticket.status)

    monkeypatch.setattr(
        escalation_service, "escalation_trigger", AsyncMock(trigger=AsyncMock(side_effect=fake_trigger))
    )

    result = asyncio.run(
        escalation_service.trigger_proactive_escalation(
            reason="A proactive check found an unresolved onboarding blocker.",
            problem="Learner still cannot access onboarding materials.",
            what_was_tried="Assistant reviewed the existing onboarding guidance.",
            context="A follow-up automation flagged the same unresolved issue.",
            suggested_next_step="Operations should verify the onboarding link and follow up.",
            summary="A proactive check found an unresolved onboarding blocker.",
            user_goal="Access the onboarding materials.",
        )
    )

    assert result.triggered is True
    assert captured_request is not None
    assert captured_request.source == EscalationSource.PROACTIVE


def test_escalate_to_human_tool_triggers_answering_escalation(monkeypatch: pytest.MonkeyPatch):
    async def fake_trigger_answering_escalation(**kwargs):
        assert kwargs["session_id"] == "session_123"
        assert kwargs["user_id"] == "user_456"
        assert kwargs["problem"] == "Learner cannot find the assignment deadline."
        return EscalationTriggerResult(
            triggered=True,
            status=TicketStatus.OPEN,
            ticket_id="esc_456",
            message="Escalation captured.",
        )

    monkeypatch.setattr(
        escalate_to_human_module,
        "trigger_answering_escalation",
        fake_trigger_answering_escalation,
    )

    result = asyncio.run(
        escalate_to_human.ainvoke(
            {
                "reason": "No grounded answer found in approved Operations materials.",
                "problem": "Learner cannot find the assignment deadline.",
                "what_was_tried": "Assistant searched approved materials.",
                "context": "The learner asked about the current sprint assignment deadline.",
                "suggested_next_step": "Operations should confirm the deadline.",
                "summary": "Learner needs clarification on an assignment deadline.",
                "user_goal": "Know when the assignment is due.",
                "session_id": "session_123",
                "user_id": "user_456",
            }
        )
    )

    assert "operations team" in result.lower()
    assert "esc_456" in result

# ---------------------------------------------------------------------------
# Week 3: escalation detector
# ---------------------------------------------------------------------------


def _message(
    role: str,
    content: str,
    *,
    grounding: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a test-friendly user or assistant message."""
    message: dict[str, object] = {"role": role, "content": content}
    if grounding is not None:
        message["additional_kwargs"] = {"grounding": grounding}
    return message


def _failed_answer(reason: str = "no_relevant_sources") -> dict[str, object]:
    """Build the structured failure contract emitted by the answer node."""
    return _message(
        "assistant",
        "I could not find enough information in the approved materials.",
        grounding={
            "grounded": False,
            "needs_escalation": True,
            "escalation_reason": reason,
        },
    )


def _grounded_answer() -> dict[str, object]:
    """Build a successful answer that resets the recent failure sequence."""
    return _message(
        "assistant",
        "The workshop starts at 7 PM.",
        grounding={
            "grounded": True,
            "needs_escalation": False,
            "escalation_reason": None,
        },
    )


def test_detector_does_not_escalate_normal_conversation():
    decision = detect_escalation(
        {
            "messages": [
                _message("user", "When is the next workshop?"),
                _grounded_answer(),
            ]
        }
    )

    assert decision.should_escalate is False
    assert decision.trigger is None
    assert decision.failure_count == 0


def test_detector_gives_explicit_request_highest_priority():
    decision = detect_escalation(
        {
            "messages": [
                _message("user", "What is the deadline?"),
                _failed_answer(),
                _message("user", "This is useless. Please connect me to a human."),
            ]
        },
        repeated_failure_threshold=1,
    )

    assert decision.should_escalate is True
    assert decision.trigger is EscalationTrigger.EXPLICIT_REQUEST


def test_detector_ignores_a_negated_ticket_request():
    decision = detect_escalation(
        {"messages": [_message("user", "Do not open a ticket; just show me the schedule.")]}
    )

    assert decision.should_escalate is False


def test_detector_keeps_positive_request_after_a_negation():
    decision = detect_escalation(
        {
            "messages": [
                _message(
                    "user",
                    "Don't open a ticket, but connect me to a human representative.",
                )
            ]
        }
    )

    assert decision.should_escalate is True
    assert decision.trigger is EscalationTrigger.EXPLICIT_REQUEST


def test_detector_detects_clear_frustration():
    decision = detect_escalation(
        {"messages": [_message("user", "I'm very frustrated; you are not helping.")]}
    )

    assert decision.should_escalate is True
    assert decision.trigger is EscalationTrigger.FRUSTRATION


def test_detector_detects_unknown_answer_from_grounding_metadata():
    decision = detect_escalation(
        {
            "messages": [
                _message("user", "What is the official project deadline?"),
                _failed_answer("insufficient_context"),
            ]
        }
    )

    assert decision.should_escalate is True
    assert decision.trigger is EscalationTrigger.UNKNOWN_ANSWER
    assert decision.failure_count == 1
    assert "insufficient_context" in decision.reason


def test_detector_detects_repeated_failures():
    decision = detect_escalation(
        {
            "messages": [
                _message("user", "What is the deadline?"),
                _failed_answer(),
                _message("user", "Can you check again?"),
                _failed_answer("invalid_citations"),
            ]
        }
    )

    assert decision.should_escalate is True
    assert decision.trigger is EscalationTrigger.REPEATED_FAILURES
    assert decision.failure_count == 2


def test_detector_grounded_answer_resets_older_failures():
    decision = detect_escalation(
        {
            "messages": [
                _message("user", "Question one"),
                _failed_answer(),
                _message("user", "Question two"),
                _failed_answer(),
                _message("user", "When is the workshop?"),
                _grounded_answer(),
            ]
        }
    )

    assert decision.should_escalate is False
    assert decision.failure_count == 0


def test_detector_does_not_reuse_old_failure_for_new_question():
    decision = detect_escalation(
        {
            "messages": [
                _message("user", "What was the old deadline?"),
                _failed_answer(),
                _message("user", "Where can I find the onboarding form?"),
            ]
        }
    )

    assert decision.should_escalate is False


@pytest.mark.parametrize(
    "options",
    [
        {"repeated_failure_threshold": 0},
        {"recent_message_window": 0},
    ],
)
def test_detector_rejects_invalid_numeric_configuration(options: dict[str, int]):
    with pytest.raises(ValueError):
        detect_escalation({"messages": []}, **options)


# ---------------------------------------------------------------------------
# Week 3: ticket schemas
# ---------------------------------------------------------------------------


def _ops_ticket_payload() -> dict[str, object]:
    """Build a valid flattened ticket payload for Week 3 schemas."""
    return {
        "id": "esc_123abc",
        "source": "answering",
        "reason": "The grounded answer could not resolve the request.",
        "status": "open",
        "problem": "Learner cannot find the assignment deadline.",
        "what_was_tried": "The assistant searched approved materials.",
        "context": "No confirmed deadline was available.",
        "suggested_next_step": "Operations should verify the deadline.",
        "summary": "The learner needs a verified deadline.",
        "user_goal": "Confirm the assignment deadline.",
        "key_facts": ["No approved source contained the deadline."],
        "assistant_actions": ["Searched approved materials."],
        "open_questions": ["What is the official deadline?"],
        "privacy_note": "The raw transcript is excluded.",
        "session_id": "session_123",
        "user_id": "user_456",
        "created_at": datetime.now(timezone.utc),
    }


def test_ops_ticket_accepts_database_id_alias():
    ticket = ticket_schema.OpsTicket.model_validate(_ops_ticket_payload())

    assert ticket.ticket_id == "esc_123abc"
    assert ticket.source is EscalationSource.ANSWERING
    assert ticket.status is TicketStatus.OPEN


def test_ops_ticket_rejects_invalid_id_and_private_extra_fields():
    invalid_id = _ops_ticket_payload()
    invalid_id["id"] = "ticket-123"

    with pytest.raises(ValidationError):
        ticket_schema.OpsTicket.model_validate(invalid_id)

    private_payload = _ops_ticket_payload()
    private_payload["raw_transcript"] = "The complete chat must not be exposed."

    with pytest.raises(ValidationError):
        ticket_schema.OpsTicket.model_validate(private_payload)


def test_ops_ticket_limits_privacy_scoped_summary_lists():
    payload = _ops_ticket_payload()
    payload["open_questions"] = [f"Question {index}" for index in range(6)]

    with pytest.raises(ValidationError):
        ticket_schema.OpsTicket.model_validate(payload)


def test_ticket_status_update_validates_status_and_rejects_extra_fields():
    update = ticket_schema.TicketStatusUpdate(status="resolved")

    assert update.status is TicketStatus.RESOLVED

    with pytest.raises(ValidationError):
        ticket_schema.TicketStatusUpdate.model_validate(
            {"status": "resolved", "raw_transcript": "not allowed"}
        )


def test_ticket_list_response_enforces_page_size_limit():
    response = ticket_schema.TicketListResponse()

    assert response.tickets == []
    assert response.limit == 50

    with pytest.raises(ValidationError):
        ticket_schema.TicketListResponse(limit=101)


# ---------------------------------------------------------------------------
# Week 3: public ticket API seam
# ---------------------------------------------------------------------------


def test_week3_api_reexports_the_registered_v1_implementation():
    assert week3_ticket_api.router is v1_tickets_api.router
    assert week3_ticket_api.OpsTicket is v1_tickets_api.OpsTicket
    assert week3_ticket_api.TicketListResponse is v1_tickets_api.TicketListResponse
    assert week3_ticket_api.TicketDetailResponse is v1_tickets_api.TicketDetailResponse
    assert week3_ticket_api.list_ops_tickets is v1_tickets_api.list_ops_tickets
    assert week3_ticket_api.view_ops_ticket is v1_tickets_api.view_ops_ticket
    assert week3_ticket_api.resolve_ops_ticket is v1_tickets_api.resolve_ops_ticket


def test_week3_api_exposes_authenticated_rate_limited_ticket_routes():
    routes = {
        (route.path, frozenset(route.methods or set())): route
        for route in week3_ticket_api.router.routes
        if isinstance(route, APIRoute)
    }

    required_routes = [
        routes[("", frozenset({"GET"}))],
        routes[("/{ticket_id}", frozenset({"GET"}))],
        routes[("/{ticket_id}/resolve", frozenset({"PATCH"}))],
    ]

    for route in required_routes:
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert v1_tickets_api.get_current_user in dependency_calls

    for endpoint_name in (
        "app.api.v1.tickets.list_ops_tickets",
        "app.api.v1.tickets.view_ops_ticket",
        "app.api.v1.tickets.resolve_ops_ticket",
    ):
        assert v1_tickets_api.limiter._route_limits[endpoint_name]