"""Entry point for the Week 3 retrieval-grounded Q&A pipeline.

The graph boundary deliberately delegates to the existing, tested retriever and
citation validator.  A caller never receives a model-only answer: it gets a
validated answer with sources or the standard honest refusal.
"""

from pydantic import BaseModel, Field

from app.graph.nodes.answer import AnswerOutcome, SourceAttribution, generate_grounded_answer


class QAResult(BaseModel):
    """Safe Q&A result suitable for HTTP, graph, and stream callers."""

    answer: str
    grounded: bool
    needs_escalation: bool
    escalation_reason: str | None = None
    sources: list[SourceAttribution] = Field(default_factory=list)


def _to_result(outcome: AnswerOutcome) -> QAResult:
    return QAResult(**outcome.model_dump())


async def answer_question(question: str, *, cohort: str) -> QAResult:
    """Answer only when approved cohort-scoped material supports the answer."""
    return _to_result(await generate_grounded_answer(question, cohort=cohort))


__all__ = ["QAResult", "answer_question"]
