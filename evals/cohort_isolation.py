"""evals/cohort_isolation.py.

Evaluation suite to verify strict cohort isolation and zero cross-cohort data leakage.
"""

from typing import Any, Dict, List


def scope_retrieval_by_cohort(query: str, cohort_id: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filters retrieved documents to strictly ensure they belong to the specified cohort_id.

    Prevents cross-cohort data leakage across vector searches and knowledge base tools.
    """
    if not cohort_id:
        raise ValueError("cohort_id must be provided for cohort-scoped retrieval")

    return [
        doc
        for doc in docs
        if doc.get("cohort_id") == cohort_id or doc.get("metadata", {}).get("cohort_id") == cohort_id
    ]


def evaluate_cohort_isolation(retrieved_docs: List[Dict[str, Any]], target_cohort_id: str) -> Dict[str, Any]:
    """Evaluates whether any documents from outside the target cohort were retrieved.

    Returns isolation metrics and flags any leaked document IDs.
    """
    leaked_docs = [
        doc
        for doc in retrieved_docs
        if doc.get("cohort_id") != target_cohort_id and doc.get("metadata", {}).get("cohort_id") != target_cohort_id
    ]

    total = len(retrieved_docs)
    leaked_count = len(leaked_docs)
    isolation_score = (total - leaked_count) / total if total > 0 else 1.0

    return {
        "isolation_score": isolation_score,
        "total_retrieved": total,
        "leaked_count": leaked_count,
        "leaked_docs": leaked_docs,
        "passed": leaked_count == 0,
    }
