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


def evaluate_qa_suite(cases_and_results: list[tuple[QAEvalCase, QAResult]]) -> dict[str, float | int]:
    """Evaluate a batch of Q&A cases and results against target metrics.

    Targets: >=90% grounding eval success, ~0% fabricated-answer rate.
    """
    if not cases_and_results:
        return {"grounding_success_rate": 1.0, "fabricated_answer_rate": 0.0, "total_cases": 0}

    passed = sum(1 for case, res in cases_and_results if evaluate_result(case, res))
    fabricated = sum(1 for case, res in cases_and_results if not case.expect_grounded and res.grounded)
    total = len(cases_and_results)

    return {
        "grounding_success_rate": passed / total,
        "fabricated_answer_rate": fabricated / total,
        "total_cases": total,
    }


__all__ = ["QA_SUITE", "QAEvalCase", "evaluate_qa_suite", "evaluate_result"]

