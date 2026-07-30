"""Cohort scoping utility for knowledge retrieval and state management."""

from typing import Any, Dict, List, Optional


def scope_retrieval_by_cohort(
    query: str,
    cohort_id: Optional[str],
    all_documents: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter retrieved documents to ensure strict isolation by cohort_id.

    If cohort_id is None or empty, returns an empty list to prevent cross-cohort leaks.
    """
    if not cohort_id:
        return []

    scoped_docs: List[Dict[str, Any]] = []
    for doc in all_documents:
        metadata = doc.get("metadata")
        doc_cohort = doc.get("cohort_id")

        # Check primary cohort_id field or nested metadata dictionary
        if doc_cohort == cohort_id:
            scoped_docs.append(doc)
        elif isinstance(metadata, dict) and metadata.get("cohort") == cohort_id:
            scoped_docs.append(doc)

    return scoped_docs


def validate_cohort_access(user_cohort: Optional[str], target_cohort: str) -> bool:
    """Validate whether a user from user_cohort can access resources in target_cohort."""
    if not user_cohort:
        return False
    return user_cohort == target_cohort
