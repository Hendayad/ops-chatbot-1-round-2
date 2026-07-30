"""Evaluation suite for verifying strict cohort isolation and preventing answer leakage."""

from typing import Any, Dict, List

from app.cohorts.scope import scope_retrieval_by_cohort, validate_cohort_access


def evaluate_zero_leakage() -> None:
    """Evaluate that document retrieval strictly isolates documents by cohort."""
    docs: List[Dict[str, Any]] = [
        {"id": 1, "cohort_id": "cohort_a", "content": "Secret A"},
        {"id": 2, "cohort_id": "cohort_b", "content": "Secret B"},
        {"id": 3, "metadata": {"cohort": "cohort_a"}, "content": "Secret A Metadata"},
        {"id": 4, "metadata": {"cohort": "cohort_b"}, "content": "Secret B Metadata"},
    ]

    # Test cohort_a isolation
    results_a = scope_retrieval_by_cohort("query", "cohort_a", docs)
    leakage_a = [
        d for d in results_a
        if d.get("cohort_id") != "cohort_a" and d.get("metadata", {}).get("cohort") != "cohort_a"
    ]
    assert len(leakage_a) == 0, f"Cross-cohort answer leakage detected in cohort_a: {leakage_a}"
    assert len(results_a) == 2, f"Expected 2 documents for cohort_a, got {len(results_a)}"

    # Test empty / None cohort_id returns no results (no leakage)
    results_none = scope_retrieval_by_cohort("query", None, docs)
    assert len(results_none) == 0, "Retrieval with None cohort_id must return empty results!"

    results_empty = scope_retrieval_by_cohort("query", "", docs)
    assert len(results_empty) == 0, "Retrieval with empty cohort_id must return empty results!"

    # Test access validation helper
    assert validate_cohort_access("cohort_a", "cohort_a") is True
    assert validate_cohort_access("cohort_a", "cohort_b") is False
    assert validate_cohort_access(None, "cohort_a") is False

    print("Zero leakage evaluation PASSED successfully.")


if __name__ == "__main__":
    evaluate_zero_leakage()
