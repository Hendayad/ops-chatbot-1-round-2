"""Detect conversations that need an Operations handoff."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.graph import GraphState

GROUNDING_FAILURE_REASONS = frozenset(
    {
        "missing_question",
        "missing_cohort",
        "no_relevant_sources",
        "retrieval_error",
        "insufficient_context",
        "invalid_model_output",
        "invalid_citations",
        "llm_error",
    }
)

DEFAULT_REPEATED_FAILURE_THRESHOLD = 2
DEFAULT_RECENT_MESSAGE_WINDOW = 8

_EXPLICIT_REQUEST_RE = re.compile(
    r"\b(?:"
    r"(?:talk|speak|chat)\s+(?:to|with)\s+(?:a\s+)?"
    r"(?:human|person|agent|representative)"
    r"|(?:transfer|connect)\s+me\s+(?:to|with)\s+(?:a\s+)?"
    r"(?:human|person|agent|representative)"
    r"|(?:i\s+)?(?:need|want|would\s+like)\s+(?:a\s+)?"
    r"(?:human|person|agent|representative|human\s+support)"
    r"|(?:contact|reach)\s+(?:the\s+)?(?:ops|operations)(?:\s+team)?"
    r"|(?:please\s+)?escalate(?:\s+this|\s+the\s+issue)?"
    r"|(?:open|create|raise|submit)\s+(?:a\s+)?(?:support\s+)?ticket"
    r")\b",
    re.IGNORECASE,
)

_NEGATED_REQUEST_RE = re.compile(
    r"\b(?:"
    r"(?:please\s+)?(?:do\s+not|don['’]?t)\s+(?:"
    r"escalate(?:\s+this)?"
    r"|(?:open|create|raise|submit)\s+(?:a\s+)?(?:support\s+)?ticket"
    r"|(?:transfer|connect)\s+me\s+(?:to|with)\s+(?:a\s+)?"
    r"(?:human|person|agent|representative)"
    r"|(?:talk|speak|chat)\s+(?:to|with)\s+(?:a\s+)?"
    r"(?:human|person|agent|representative)"
    r"|(?:contact|reach)\s+(?:the\s+)?(?:ops|operations)(?:\s+team)?"
    r")"
    r"|(?:i\s+)?(?:do\s+not|don['’]?t)\s+(?:need|want)(?:\s+to)?\s+(?:"
    r"(?:talk|speak|chat)\s+(?:to|with)\s+(?:a\s+)?"
    r"(?:human|person|agent|representative)"
    r"|(?:a\s+)?(?:human|person|agent|representative|ticket)"
    r")"
    r"|no\s+(?:human|agent|representative|ticket)(?:\s+is)?\s+needed"
    r"|no\s+(?:human|agent|representative|ticket)(?:\s+please)?"
    r")\b",
    re.IGNORECASE,
)

_FRUSTRATION_RE = re.compile(
    r"\b(?:"
    r"i(?:['’]?m|\s+am)\s+(?:really\s+|very\s+|so\s+)?"
    r"(?:frustrated|annoyed|upset|angry)"
    r"|this\s+is\s+(?:completely\s+)?"
    r"(?:useless|not\s+helpful|going\s+nowhere)"
    r"|you(?:['’]?re|\s+are)\s+not\s+(?:helping|answering|listening)"
    r"|how\s+many\s+times\s+(?:do\s+i\s+need\s+to|must\s+i)"
    r"|i(?:['’]?ve|\s+have)\s+(?:already\s+)?asked\s+(?:this\s+)?"
    r"(?:several|multiple|many)\s+times"
    r"|(?:this|it)\s+still\s+(?:doesn['’]?t|does\s+not|isn['’]?t|is\s+not)"
    r"\s+work(?:ing)?"
    r")\b",
    re.IGNORECASE,
)

_ASSISTANT_FAILURE_PHRASES = (
    "couldn't find",
    "could not find",
    "cannot find",
    "can't find",
    "not enough information",
    "insufficient information",
    "insufficient context",
    "approved materials do not",
    "approved materials don't",
    "couldn't verify",
    "could not verify",
    "cannot verify",
    "i don't know",
    "i do not know",
    "i cannot answer",
    "i can't answer",
    "needs help from the operations team",
)


class EscalationTrigger(str, Enum):
    """Supported escalation reasons."""

    UNKNOWN_ANSWER = "unknown_answer"
    FRUSTRATION = "frustration"
    EXPLICIT_REQUEST = "explicit_request"
    REPEATED_FAILURES = "repeated_failures"


@dataclass(frozen=True, slots=True)
class EscalationDecision:
    """Result of evaluating the current conversation."""

    should_escalate: bool
    trigger: EscalationTrigger | None = None
    reason: str = ""
    failure_count: int = 0


def _get(value: object, key: str, default: Any = None) -> Any:
    """Read a field from either a mapping or an object."""
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _message_text(message: object | None) -> str:
    """Return normalized text from common message content shapes."""
    if message is None:
        return ""

    content = _get(message, "content", "")
    if isinstance(content, str):
        return " ".join(content.split())

    if not isinstance(content, Sequence) or isinstance(
        content,
        (str, bytes, bytearray),
    ):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, Mapping):
            text = block.get("text") or block.get("content")
            if isinstance(text, str):
                parts.append(text)

    return " ".join(" ".join(parts).split())


def _message_role(message: object) -> str | None:
    """Normalize user/assistant roles to human/ai."""
    role = _get(message, "type") or _get(message, "role")
    if not isinstance(role, str):
        return None

    role = role.casefold()
    return {"user": "human", "assistant": "ai"}.get(role, role)


def _grounding(message: object) -> Mapping[str, Any]:
    """Read grounding metadata emitted by the answer node."""
    metadata = _get(message, "additional_kwargs", {})
    if not isinstance(metadata, Mapping):
        return {}

    grounding = metadata.get("grounding", {})
    return grounding if isinstance(grounding, Mapping) else {}


def _messages(state: GraphState | Mapping[str, Any] | object) -> list[object]:
    """Read conversation messages from graph state or a test mapping."""
    value = _get(state, "messages", ())
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return []
    return list(value)


def _latest(messages: Sequence[object], role: str) -> tuple[int, object | None]:
    """Return the index and value of the latest message with the given role."""
    for index in range(len(messages) - 1, -1, -1):
        if _message_role(messages[index]) == role:
            return index, messages[index]
    return -1, None


def _is_explicit_request(text: str) -> bool:
    """Detect a non-negated request for human or ticket support."""
    without_negations = _NEGATED_REQUEST_RE.sub(" ", text)
    return _EXPLICIT_REQUEST_RE.search(without_negations) is not None


def _is_grounding_failure(message: object) -> bool:
    """Return whether an assistant message represents an unresolved answer."""
    grounding = _grounding(message)

    # Structured success must win over fallback text matching.
    if grounding.get("grounded") is True:
        return False

    if grounding.get("needs_escalation") is True:
        return True

    reason = grounding.get("escalation_reason")
    reason = getattr(reason, "value", reason)
    if isinstance(reason, str) and reason in GROUNDING_FAILURE_REASONS:
        return True

    text = _message_text(message).casefold()
    return any(phrase in text for phrase in _ASSISTANT_FAILURE_PHRASES)


def _recent_failure_count(
    messages: Sequence[object],
    recent_message_window: int,
) -> int:
    """Count recent failures since the latest grounded assistant answer."""
    count = 0
    for message in reversed(messages[-recent_message_window:]):
        if _message_role(message) != "ai":
            continue
        if _grounding(message).get("grounded") is True:
            break
        if _is_grounding_failure(message):
            count += 1
    return count


def detect_escalation(
    state: GraphState | Mapping[str, Any] | object,
    *,
    repeated_failure_threshold: int = DEFAULT_REPEATED_FAILURE_THRESHOLD,
    recent_message_window: int = DEFAULT_RECENT_MESSAGE_WINDOW,
) -> EscalationDecision:
    """Select the highest-priority escalation trigger for a conversation."""
    if repeated_failure_threshold < 1:
        raise ValueError("repeated_failure_threshold must be at least 1")
    if recent_message_window < 1:
        raise ValueError("recent_message_window must be at least 1")

    messages = _messages(state)
    human_index, latest_human = _latest(messages, "human")
    ai_index, latest_ai = _latest(messages, "ai")
    learner_text = _message_text(latest_human)

    if _is_explicit_request(learner_text):
        return EscalationDecision(
            True,
            EscalationTrigger.EXPLICIT_REQUEST,
            "The learner explicitly requested human or Operations support.",
        )

    failure_count = _recent_failure_count(messages, recent_message_window)
    if failure_count >= repeated_failure_threshold:
        return EscalationDecision(
            True,
            EscalationTrigger.REPEATED_FAILURES,
            f"The assistant had {failure_count} recent unresolved answer failures.",
            failure_count,
        )

    if _FRUSTRATION_RE.search(learner_text):
        return EscalationDecision(
            True,
            EscalationTrigger.FRUSTRATION,
            "The learner expressed clear frustration with the support experience.",
            failure_count,
        )

    # Do not reuse an old failed answer for a newer learner question.
    if (
        latest_ai is not None
        and ai_index > human_index
        and _is_grounding_failure(latest_ai)
    ):
        raw_reason = _grounding(latest_ai).get("escalation_reason")
        raw_reason = getattr(raw_reason, "value", raw_reason)
        reason = raw_reason if isinstance(raw_reason, str) else "unknown_answer"
        return EscalationDecision(
            True,
            EscalationTrigger.UNKNOWN_ANSWER,
            f"The grounded-answer flow could not resolve the request ({reason}).",
            max(1, failure_count),
        )

    return EscalationDecision(False)
    
__all__ = [
    "DEFAULT_RECENT_MESSAGE_WINDOW",
    "DEFAULT_REPEATED_FAILURE_THRESHOLD",
    "GROUNDING_FAILURE_REASONS",
    "EscalationDecision",
    "EscalationTrigger",
    "detect_escalation",
]