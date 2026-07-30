"""Entry point for the Week 3 retrieval-grounded Q&A pipeline.

The graph boundary deliberately delegates to the existing, tested retriever and
citation validator.  A caller never receives a model-only answer: it gets a
validated answer with sources or the standard honest refusal.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.graph.nodes.answer import (
    AnswerOutcome,
    SourceAttribution,
    answer_node,
    generate_grounded_answer,
    grounded_answer,
)
from app.schemas.graph import GraphState
from langgraph.graph import END, StateGraph


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


def build_qa_graph(*, checkpointer: Any | None = None):
    """Build a dedicated Q&A LangGraph workflow node."""
    graph = StateGraph(GraphState)
    graph.add_node("answer", grounded_answer)
    graph.set_entry_point("answer")
    graph.add_edge("answer", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "QAResult",
    "answer_node",
    "answer_question",
    "build_qa_graph",
    "grounded_answer",
]

