"""Contract tests for Week 3 Q&A entry points and evaluation suite."""

import asyncio

import pytest

from app.graph.nodes.answer import AnswerOutcome, SourceAttribution
from app.qa.graph import answer_question
from app.qa.stream import stream_answer
from evals.qa_suite import QA_SUITE, evaluate_result


def _source() -> SourceAttribution:
    return SourceAttribution(
        alias="S1",
        citation_id="source-1:0",
        source_id="source-1",
        title="Schedule",
        source="schedule.md",
        source_type="markdown",
        cohort="cohort-a",
        chunk_index=0,
        similarity=0.9,
    )


def test_qa_graph_exposes_validated_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_generate(question: str, *, cohort: str) -> AnswerOutcome:
        assert question == "When is class?"
        assert cohort == "cohort-a"
        return AnswerOutcome(answer="Friday [S1]", sources=[_source()], grounded=True, needs_escalation=False)

    monkeypatch.setattr("app.qa.graph.generate_grounded_answer", fake_generate)
    result = asyncio.run(answer_question("When is class?", cohort="cohort-a"))

    assert result.grounded is True
    assert result.sources[0].alias == "S1"
    assert evaluate_result(QA_SUITE[0], result) is True


def test_stream_waits_for_validated_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_generate(question: str, *, cohort: str) -> AnswerOutcome:
        return AnswerOutcome(answer="Line one\nLine two", grounded=False, needs_escalation=True, escalation_reason="no_relevant_sources")

    monkeypatch.setattr("app.qa.graph.generate_grounded_answer", fake_generate)
    async def collect() -> list[str]:
        return [chunk async for chunk in stream_answer("unknown", cohort="cohort-a")]

    chunks = asyncio.run(collect())
    assert "".join(chunks) == "Line one\nLine two"


def test_build_qa_graph_compiles() -> None:
    from app.qa.graph import build_qa_graph

    graph = build_qa_graph()
    assert graph is not None


def test_evaluate_qa_suite_metrics() -> None:
    from app.qa.graph import QAResult
    from evals.qa_suite import QA_SUITE, evaluate_qa_suite

    res1 = QAResult(answer="Friday [S1]", grounded=True, needs_escalation=False, sources=[_source()])
    res2 = QAResult(answer="Honest refusal", grounded=False, needs_escalation=True, escalation_reason="no_relevant_sources")
    res3 = QAResult(answer="Honest refusal", grounded=False, needs_escalation=True, escalation_reason="invalid_citations")

    cases_and_results = [
        (QA_SUITE[0], res1),
        (QA_SUITE[1], res2),
        (QA_SUITE[2], res3),
    ]

    metrics = evaluate_qa_suite(cases_and_results)
    assert metrics["grounding_success_rate"] == 1.0
    assert metrics["fabricated_answer_rate"] == 0.0
    assert metrics["total_cases"] == 3

