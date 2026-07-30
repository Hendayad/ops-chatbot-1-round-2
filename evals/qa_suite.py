"""Deterministic regression cases for the Week 3 grounded Q&A contract."""

from dataclasses import dataclass

from app.qa.graph import QAResult


@dataclass(frozen=True)
class QAEvalCase:
    name: str
    expect_grounded: bool


QA_SUITE = (
    QAEvalCase("supported answer includes sources", True),
    QAEvalCase("unknown answer is refused", False),
    QAEvalCase("invalid citation is refused", False),
)


def evaluate_result(case: QAEvalCase, result: QAResult) -> bool:
    """Check the public safety invariants without calling an LLM."""
    if result.grounded != case.expect_grounded:
        return False
    if result.grounded:
        return bool(result.sources) and not result.needs_escalation
    return result.needs_escalation and not result.sources
