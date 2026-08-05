"""Evaluate that knowledge retrieval never leaks data across cohorts.

This evaluation is deterministic and does not need PostgreSQL, pgvector, an
embedding API, or an LLM connection. It deliberately uses a repository that
returns chunks from multiple cohorts and verifies that the application keeps
only the requested cohort.

Run from the project root:

    uv run python -m evals.cohort_isolation
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from app.cohorts.config import cohort_config, is_servable_cohort
from app.cohorts.scope import find_leaked_items, scope_by_cohort
from app.graph.nodes.answer import generate_grounded_answer
from app.retrieval.retriever import KnowledgeRetriever, RetrievedChunk


def _chunk(index: int, cohort: str) -> RetrievedChunk:
    """Create one deterministic retrieved chunk."""
    return RetrievedChunk(
        source_id=f"{cohort}::schedule.md",
        title=f"{cohort} schedule",
        source="schedule.md",
        source_type="schedule",
        cohort=cohort,
        content_hash=f"hash-{cohort}",
        chunk_index=index,
        content=f"The approved deadline for {cohort} is different.",
        distance=0.1,
        similarity=0.9,
    )


class StaticEmbedder:
    """Return a fixed query vector without calling an external provider."""

    def embed_query(self, query: str) -> list[float]:
        """Return one deterministic embedding."""
        return [0.1, 0.2, 0.3]


class LeakyRepository:
    """Simulate a broken backend that returns chunks from every cohort."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        """Store the deliberately mixed chunks."""
        self.chunks = chunks

    def search(
        self,
        query_embedding: list[float],
        *,
        cohort: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Ignore the cohort argument on purpose to test defense in depth."""
        del query_embedding, cohort
        return self.chunks[:limit]


def _result(case: str, passed: bool, **details: Any) -> dict[str, Any]:
    """Create one evaluation result."""
    return {
        "case": case,
        "passed": passed,
        "isolation_score": 1.0 if passed else 0.0,
        **details,
    }


def evaluate_scope_rules() -> list[dict[str, Any]]:
    """Verify the shared cohort filtering helpers."""
    documents = [
        {"id": 1, "cohort": "cohort-a"},
        {"id": 2, "cohort": "cohort-b"},
        {"id": 3, "metadata": {"cohort_id": "cohort-a"}},
        {"id": 4, "metadata": {"cohort": "cohort-b"}},
        {"id": 5},
    ]
    results: list[dict[str, Any]] = []

    for cohort in ("cohort-a", "cohort-b"):
        scoped = scope_by_cohort(documents, cohort)
        leaked = find_leaked_items(scoped, cohort)
        results.append(
            _result(
                f"scope_{cohort}",
                len(scoped) == 2 and not leaked,
                returned=len(scoped),
                leaked=leaked,
            )
        )

    for missing in (None, "", "   "):
        scoped = scope_by_cohort(documents, missing)
        results.append(
            _result(
                f"scope_missing_{missing!r}",
                scoped == [],
                returned=len(scoped),
            )
        )

    return results


def evaluate_retriever() -> list[dict[str, Any]]:
    """Verify that the real retriever removes foreign-cohort chunks."""
    mixed_chunks = [
        _chunk(0, "cohort-a"),
        _chunk(0, "cohort-b"),
        _chunk(1, "cohort-a"),
        _chunk(1, "cohort-b"),
    ]
    retriever = KnowledgeRetriever(
        repository=LeakyRepository(mixed_chunks),
        embedder=StaticEmbedder(),
    )

    results: list[dict[str, Any]] = []
    for cohort in ("cohort-a", "cohort-b"):
        retrieved = retriever.retrieve_sync(
            "When is the final project deadline?",
            cohort=cohort,
        )
        leaked = find_leaked_items(retrieved, cohort)
        results.append(
            _result(
                f"retriever_{cohort}",
                len(retrieved) == 2 and not leaked,
                returned=len(retrieved),
                leaked=[chunk.citation_id for chunk in leaked],
            )
        )

    missing = retriever.retrieve_sync(
        "When is the final project deadline?",
        cohort="",
    )
    results.append(
        _result(
            "retriever_missing_cohort",
            missing == [],
            returned=len(missing),
        )
    )
    return results


def evaluate_configuration_and_refusals() -> list[dict[str, Any]]:
    """Verify configured cohorts and safe missing/unknown-cohort refusals."""
    original_path = cohort_config.config_path

    with tempfile.TemporaryDirectory() as temp_directory:
        config_path = Path(temp_directory) / "cohorts_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "cohort-a": {
                        "name": "Cohort A",
                        "materials_root": "materials/cohort-a",
                        "enabled": True,
                        "materials": [],
                    },
                    "cohort-b": {
                        "name": "Cohort B",
                        "materials_root": "materials/cohort-b",
                        "enabled": True,
                        "materials": [],
                    },
                }
            ),
            encoding="utf-8",
        )

        cohort_config.config_path = str(config_path)
        try:
            known_a = is_servable_cohort("cohort-a")
            known_b = is_servable_cohort("cohort-b")
            unknown = is_servable_cohort("cohort-x")

            missing_outcome = asyncio.run(
                generate_grounded_answer(
                    "When is the final project deadline?",
                    cohort="",
                )
            )
            unknown_outcome = asyncio.run(
                generate_grounded_answer(
                    "When is the final project deadline?",
                    cohort="cohort-x",
                )
            )
        finally:
            cohort_config.config_path = original_path

    return [
        _result(
            "configuration_known_cohorts",
            known_a and known_b,
        ),
        _result(
            "configuration_unknown_cohort",
            not unknown,
        ),
        _result(
            "answer_missing_cohort_refusal",
            (
                not missing_outcome.grounded
                and missing_outcome.needs_escalation
                and missing_outcome.escalation_reason == "missing_cohort"
            ),
            reason=missing_outcome.escalation_reason,
        ),
        _result(
            "answer_unknown_cohort_refusal",
            (
                not unknown_outcome.grounded
                and unknown_outcome.needs_escalation
                and unknown_outcome.escalation_reason == "unknown_cohort"
            ),
            reason=unknown_outcome.escalation_reason,
        ),
    ]


def run_evaluation() -> list[dict[str, Any]]:
    """Run all cohort-isolation checks."""
    return [
        *evaluate_scope_rules(),
        *evaluate_retriever(),
        *evaluate_configuration_and_refusals(),
    ]


def main() -> None:
    """Print the report and exit with an error when any check fails."""
    results = run_evaluation()

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"[{status}] {result['case']} "
            f"- isolation_score={result['isolation_score']:.2f}"
        )

    failed = [result for result in results if not result["passed"]]
    if failed:
        print(f"\nCross-cohort leakage or unsafe behavior found in {len(failed)} case(s).")
        raise SystemExit(1)

    print(f"\nAll {len(results)} checks passed - zero cross-cohort leakage detected.")


if __name__ == "__main__":
    main()