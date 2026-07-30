"""Cohort isolation evaluation (M10 / F3.4).

Verifies the acceptance signal "no answer leakage between cohorts" against the
code that actually ships, at three levels:

1. the isolation rules themselves (``app.cohorts.scope``);
2. the M02 retrieval path (``app.retrieval.retriever.KnowledgeRetriever``),
   driven by a deliberately leaky repository that returns both cohorts, which
   is what a broken SQL filter or a wrong custom backend would look like; and
3. the answering path (``app.graph.nodes.answer``) — chunk scoping, citation
   validation, and cohort resolution — because an isolated retriever is not
   enough if the answer node would cite a foreign source anyway.

Nothing here re-implements the rules it is testing. Every function under test is
imported from the application.

Run directly:  python -m evals.cohort_isolation
"""

import asyncio
import json
import os
import tempfile
from typing import Any

from app.cohorts.config import cohort_config, is_servable_cohort
from app.cohorts.scope import find_leaked_items, scope_by_cohort, validate_cohort_access
from app.graph.nodes.answer import (
    _citations_are_valid,
    _deduplicate_and_scope_chunks,
    generate_grounded_answer,
    resolve_cohort,
)
from app.prompts.grounding import GroundedAnswer
from app.retrieval.retriever import KnowledgeRetriever, RetrievedChunk

# Documents deliberately mix the two supported metadata shapes so isolation is
# proven for both: a top-level cohort key, and a nested metadata dictionary.
SAMPLE_DOCUMENTS: list[dict[str, Any]] = [
    {"id": 1, "cohort": "cohort-a", "content": "Cohort A schedule"},
    {"id": 2, "cohort": "cohort-b", "content": "Cohort B schedule"},
    {"id": 3, "metadata": {"cohort": "cohort-a"}, "content": "Cohort A FAQ"},
    {"id": 4, "metadata": {"cohort_id": "cohort-b"}, "content": "Cohort B FAQ"},
    {"id": 5, "content": "Unscoped document with no cohort at all"},
]


def _chunk(index: int, cohort: str) -> RetrievedChunk:
    """Build one realistic retrieved chunk owned by the given cohort."""
    return RetrievedChunk(
        source_id=f"{cohort}/handbook",
        title=f"{cohort} handbook",
        source=f"materials/{cohort}/handbook.md",
        source_type="faq",
        cohort=cohort,
        content_hash="hash",
        chunk_index=index,
        content=f"Approved guidance belonging to {cohort}.",
        distance=0.1,
        similarity=0.9,
    )


class LeakyChunkRepository:
    """A search backend that ignores the cohort filter it was given.

    This stands in for the failure the isolation layer exists to catch: a bad
    SQL filter, a cache keyed without the cohort, or a third-party backend.
    """

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        """Store the chunks this repository will always return."""
        self._chunks = chunks

    def search(self, query_embedding: list[float], *, cohort: str, limit: int) -> list[RetrievedChunk]:
        """Return every stored chunk regardless of the requested cohort."""
        return self._chunks[:limit]


class StaticEmbedder:
    """Embedder returning a fixed vector so no network call is made."""

    def embed_query(self, query: str) -> list[float]:
        """Return a constant embedding for any query."""
        return [0.1, 0.2, 0.3]


def evaluate_cohort_isolation(retrieved: list[Any], target_cohort: str) -> dict[str, Any]:
    """Score one retrieval result for cross-cohort leakage.

    Returns the leaked records themselves, not just a count, so a failing run
    names exactly which documents escaped their cohort.
    """
    leaked = find_leaked_items(retrieved, target_cohort)
    total = len(retrieved)
    isolation_score = (total - len(leaked)) / total if total else 1.0

    return {
        "target_cohort": target_cohort,
        "total_retrieved": total,
        "leaked_count": len(leaked),
        "leaked_items": leaked,
        "isolation_score": isolation_score,
        "passed": not leaked,
    }


def _report(case: str, passed: bool, **extra: Any) -> dict[str, Any]:
    """Build one uniform report row."""
    return {"case": case, "passed": passed, "isolation_score": 1.0 if passed else 0.0, **extra}


def evaluate_scope_rules() -> list[dict[str, Any]]:
    """Level 1: the shared isolation rules in app.cohorts.scope."""
    reports: list[dict[str, Any]] = []

    # Each cohort sees only its own two documents.
    for cohort in ("cohort-a", "cohort-b"):
        scoped = scope_by_cohort(SAMPLE_DOCUMENTS, cohort)
        report = evaluate_cohort_isolation(scoped, cohort)
        report["case"] = f"scope_rules_{cohort}"
        report["expected_count"] = 2
        report["passed"] = report["passed"] and len(scoped) == 2
        reports.append(report)

    # A missing cohort must return nothing rather than everything.
    for missing in (None, "", "   "):
        scoped = scope_by_cohort(SAMPLE_DOCUMENTS, missing)
        reports.append(
            _report(
                f"scope_rules_missing_cohort_{missing!r}",
                not scoped,
                target_cohort=missing,
                leaked_count=len(scoped),
                leaked_items=scoped,
            )
        )

    # Access validation refuses every cross-cohort combination.
    access_checks = [
        ("cohort-a", "cohort-a", True),
        ("cohort-a", "cohort-b", False),
        (None, "cohort-a", False),
        ("", "cohort-a", False),
    ]
    access_passed = all(validate_cohort_access(user, target) is expected for user, target, expected in access_checks)
    reports.append(_report("scope_rules_validate_access", access_passed, checks=len(access_checks)))

    return reports


def evaluate_retrieval_path() -> list[dict[str, Any]]:
    """Level 2: the real M02 retriever, fed a repository that leaks."""
    reports: list[dict[str, Any]] = []

    mixed_chunks = [_chunk(0, "cohort-a"), _chunk(1, "cohort-b"), _chunk(2, "cohort-a"), _chunk(3, "cohort-b")]
    retriever = KnowledgeRetriever(
        repository=LeakyChunkRepository(mixed_chunks),
        embedder=StaticEmbedder(),
    )

    for cohort in ("cohort-a", "cohort-b"):
        results = retriever.retrieve_sync("when is the deadline", cohort=cohort)
        report = evaluate_cohort_isolation(results, cohort)
        report["case"] = f"retriever_drops_foreign_chunks_{cohort}"
        # Half the corpus belongs to this cohort; returning zero would pass the
        # leakage check while silently breaking retrieval, so require both.
        report["passed"] = report["passed"] and len(results) == 2
        reports.append(report)

    # An empty cohort must not reach the repository at all.
    unscoped = retriever.retrieve_sync("when is the deadline", cohort="")
    reports.append(_report("retriever_refuses_empty_cohort", not unscoped, leaked_items=unscoped))

    return reports


def evaluate_answer_path() -> list[dict[str, Any]]:
    """Level 3: the answering node's scoping, citations, and cohort resolution."""
    reports: list[dict[str, Any]] = []

    mixed_chunks = [_chunk(0, "cohort-a"), _chunk(1, "cohort-b")]

    # Chunk scoping inside the node drops the foreign chunk before prompting.
    scoped = _deduplicate_and_scope_chunks(mixed_chunks, cohort="cohort-a")
    scoping_passed = len(scoped) == 1 and scoped[0].cohort == "cohort-a"
    reports.append(_report("answer_node_scopes_chunks", scoping_passed, kept=[chunk.cohort for chunk in scoped]))

    # Citation validation rejects an alias whose source belongs to another
    # cohort, and rejects one whose source carries no cohort at all.
    response = GroundedAnswer(answer="The deadline is Friday [S1].", citations=["S1"], sufficient_context=True)
    foreign_map = {"S1": _chunk(1, "cohort-b")}
    own_map = {"S1": _chunk(0, "cohort-a")}
    unscoped_map = {"S1": _chunk(0, "")}

    citation_passed = (
        _citations_are_valid(response, own_map, cohort="cohort-a") is True
        and _citations_are_valid(response, foreign_map, cohort="cohort-a") is False
        and _citations_are_valid(response, unscoped_map, cohort="cohort-a") is False
    )
    reports.append(_report("answer_node_rejects_foreign_citations", citation_passed, checks=3))

    # A request that carries no cohort must resolve to "" and refuse, rather
    # than falling back to some other cohort's material.
    resolved = resolve_cohort({"messages": []}, None)
    outcome = asyncio.run(generate_grounded_answer("when is the deadline", cohort=""))
    refusal_passed = resolved == "" and outcome.escalation_reason == "missing_cohort" and not outcome.grounded
    reports.append(_report("answer_node_refuses_without_cohort", refusal_passed, resolved_cohort=resolved))

    return reports


def evaluate_config_gating() -> list[dict[str, Any]]:
    """Level 4: a cohort absent from the configuration is served nothing.

    Isolation has two halves. app.cohorts.scope decides whether an item belongs
    to a cohort; the configuration decides whether the cohort exists at all. A
    cohort with no config entry has no materials of its own, so answering it
    could only mean serving somebody else's.
    """
    original_path = cohort_config.config_path
    with tempfile.TemporaryDirectory() as directory:
        config_path = os.path.join(directory, "cohorts_config.json")
        with open(config_path, "w", encoding="utf-8") as config_file:
            json.dump({"cohort-a": {"name": "A", "materials_root": "materials/a"}}, config_file)

        cohort_config.config_path = config_path
        try:
            known = is_servable_cohort("cohort-a")
            unknown = is_servable_cohort("cohort-zzz")
            outcome = asyncio.run(generate_grounded_answer("when is the deadline", cohort="cohort-zzz"))
        finally:
            cohort_config.config_path = original_path

    gating_passed = known is True and unknown is False and outcome.escalation_reason == "unknown_cohort"
    return [_report("config_gate_refuses_unconfigured_cohort", gating_passed, refusal=outcome.escalation_reason)]


def run_evaluation() -> list[dict[str, Any]]:
    """Run every isolation case and return one report per case."""
    return evaluate_scope_rules() + evaluate_retrieval_path() + evaluate_answer_path() + evaluate_config_gating()


def main() -> None:
    """Print a readable report and raise when any case leaks."""
    reports = run_evaluation()

    for report in reports:
        status = "PASS" if report["passed"] else "FAIL"
        # Plain ASCII only: this runs in Windows consoles that mangle dashes.
        print(f"[{status}] {report['case']} - isolation_score={report['isolation_score']:.2f}")
        if not report["passed"]:
            print(f"         leaked: {report.get('leaked_items')}")

    failed = [report for report in reports if not report["passed"]]
    if failed:
        raise AssertionError(f"cross-cohort leakage detected in {len(failed)} case(s)")

    print(f"\nAll {len(reports)} isolation cases passed - no cross-cohort leakage.")


if __name__ == "__main__":
    main()
