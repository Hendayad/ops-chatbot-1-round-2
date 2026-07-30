"""Cohort isolation evaluation (M10 / F3.4).

Verifies the acceptance signal "no answer leakage between cohorts" against the
rules that production actually uses — ``app.cohorts.scope`` — rather than a
copy of them. The retriever and the grounded-answer node both delegate their
filtering to those same functions, so a passing run here means the real path
is isolated too.

Run directly:  python -m evals.cohort_isolation
"""

from typing import Any

from app.cohorts.scope import find_leaked_items, scope_by_cohort, validate_cohort_access

# Documents deliberately mix the two supported metadata shapes so isolation is
# proven for both: a top-level cohort key, and a nested metadata dictionary.
SAMPLE_DOCUMENTS: list[dict[str, Any]] = [
    {"id": 1, "cohort": "cohort-a", "content": "Cohort A schedule"},
    {"id": 2, "cohort": "cohort-b", "content": "Cohort B schedule"},
    {"id": 3, "metadata": {"cohort": "cohort-a"}, "content": "Cohort A FAQ"},
    {"id": 4, "metadata": {"cohort_id": "cohort-b"}, "content": "Cohort B FAQ"},
    {"id": 5, "content": "Unscoped document with no cohort at all"},
]


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


def run_evaluation() -> list[dict[str, Any]]:
    """Run every isolation case and return one report per case."""
    reports: list[dict[str, Any]] = []

    # Case 1 and 2: each cohort sees only its own two documents.
    for cohort in ("cohort-a", "cohort-b"):
        scoped = scope_by_cohort(SAMPLE_DOCUMENTS, cohort)
        report = evaluate_cohort_isolation(scoped, cohort)
        report["case"] = f"scoped_retrieval_{cohort}"
        report["expected_count"] = 2
        report["passed"] = report["passed"] and len(scoped) == 2
        reports.append(report)

    # Case 3: a missing cohort must return nothing rather than everything.
    for missing in (None, "", "   "):
        scoped = scope_by_cohort(SAMPLE_DOCUMENTS, missing)
        reports.append(
            {
                "case": f"missing_cohort_{missing!r}",
                "target_cohort": missing,
                "total_retrieved": len(scoped),
                "leaked_count": len(scoped),
                "leaked_items": scoped,
                "isolation_score": 1.0 if not scoped else 0.0,
                "passed": not scoped,
            }
        )

    # Case 4: access validation refuses every cross-cohort combination.
    access_checks = [
        ("cohort-a", "cohort-a", True),
        ("cohort-a", "cohort-b", False),
        (None, "cohort-a", False),
        ("", "cohort-a", False),
    ]
    access_passed = all(validate_cohort_access(user, target) is expected for user, target, expected in access_checks)
    reports.append(
        {
            "case": "validate_cohort_access",
            "checks": len(access_checks),
            "isolation_score": 1.0 if access_passed else 0.0,
            "passed": access_passed,
        }
    )

    return reports


def main() -> None:
    """Print a readable report and raise when any case leaks."""
    reports = run_evaluation()

    for report in reports:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"[{status}] {report['case']} — isolation_score={report['isolation_score']:.2f}")
        if not report["passed"]:
            print(f"         leaked: {report.get('leaked_items')}")

    failed = [report for report in reports if not report["passed"]]
    if failed:
        raise AssertionError(f"cross-cohort leakage detected in {len(failed)} case(s)")

    print(f"\nAll {len(reports)} isolation cases passed — no cross-cohort leakage.")


if __name__ == "__main__":
    main()
