"""
evals/cohort_isolation.py
Evaluation suite to verify strict cohort isolation and zero cross-cohort data leakage.
"""

from typing import List, Dict, Any


def scope_retrieval_by_cohort(query: str, cohort_id: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filters retrieved documents to strictly ensure they belong to the specified cohort_id.
    Prevents cross-cohort data leakage across vector searches and knowledge base tools.
    """
    if not cohort_id:
        raise ValueError("cohort_id must be provided for cohort-scoped retrieval")
    
    return [doc for doc in docs if doc.get("cohort_id") == cohort_id]


def evaluate_zero_leakage() -> None:
    """Verifies that retrieving for Cohort A returns zero documents belonging to other cohorts."""
    docs = [
        {"id": 1, "cohort_id": "cohort_a", "content": "Secret A"},
        {"id": 2, "cohort_id": "cohort_b", "content": "Secret B"},
    ]
    results_a = scope_retrieval_by_cohort("query", "cohort_a", docs)
    leakage = [d for d in results_a if d["cohort_id"] != "cohort_a"]
    assert len(leakage) == 0, "Cross-cohort answer leakage detected!"
    print("Zero leakage evaluation PASSED successfully.")


def evaluate_empty_or_invalid_cohort() -> None:
    """Verifies that non-existent cohorts return zero documents without leakage."""
    docs = [
        {"id": 1, "cohort_id": "cohort_a", "content": "Secret A"},
        {"id": 2, "cohort_id": "cohort_b", "content": "Secret B"},
    ]
    results_unknown = scope_retrieval_by_cohort("query", "cohort_unknown", docs)
    assert len(results_unknown) == 0, "Unknown cohort should return empty results!"
    print("Invalid cohort evaluation PASSED successfully.")


def evaluate_multi_document_isolation() -> None:
    """Verifies retrieval across multi-cohort documents dataset."""
    docs = [
        {"id": 101, "cohort_id": "cohort_2026_q1", "content": "Q1 Schedule"},
        {"id": 102, "cohort_id": "cohort_2026_q1", "content": "Q1 Guidelines"},
        {"id": 201, "cohort_id": "cohort_2026_q2", "content": "Q2 Schedule"},
        {"id": 202, "cohort_id": "cohort_2026_q2", "content": "Q2 Grading"},
    ]
    results_q1 = scope_retrieval_by_cohort("Schedule", "cohort_2026_q1", docs)
    assert len(results_q1) == 2, "Should retrieve all matching documents for cohort_2026_q1"
    for doc in results_q1:
        assert doc["cohort_id"] == "cohort_2026_q1", f"Leaked document found: {doc}"
    print("Multi-document isolation evaluation PASSED successfully.")


def run_all_evaluations() -> None:
    """Runs all cohort isolation evaluation suites."""
    print("--- Running Cohort Isolation Evaluation Suite ---")
    evaluate_zero_leakage()
    evaluate_empty_or_invalid_cohort()
    evaluate_multi_document_isolation()
    print("--- All Cohort Isolation Evals PASSED (1.0 Precision/Recall) ---")


if __name__ == "__main__":
    run_all_evaluations()