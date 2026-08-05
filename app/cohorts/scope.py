"""Cohort isolation rules — the single source of truth for M10 (F3.4).

Every layer that touches cohort-owned data imports its rules from here, so
the definition of "same cohort" exists in exactly one place:

* ``app/retrieval/retriever.py`` — defence-in-depth filter after the SQL query
* ``app/graph/nodes/answer.py``  — chunk scoping and citation validation
* ``evals/cohort_isolation.py``  — leakage verification

The rules fail closed: a missing or empty cohort never matches anything, so a
bug upstream produces zero results rather than another cohort's data.
"""

from typing import Any

# Keys a raw dictionary may use to carry its cohort. Both spellings exist in
# stored material metadata, so isolation must recognise either.
_COHORT_KEYS = ("cohort", "cohort_id")


def normalize_cohort(cohort: str | None) -> str:
    """Return a cohort id stripped of surrounding whitespace, or "" if absent."""
    if not cohort:
        return ""
    return cohort.strip().casefold()


def is_same_cohort(candidate: str | None, expected: str | None) -> bool:
    """Return True only when both cohorts are present and identical.

    An empty cohort on either side returns False, so unscoped data can never
    match a scoped request.
    """
    normalized_candidate = normalize_cohort(candidate)
    normalized_expected = normalize_cohort(expected)
    if not normalized_candidate or not normalized_expected:
        return False
    return normalized_candidate == normalized_expected


def validate_cohort_access(user_cohort: str | None, target_cohort: str | None) -> bool:
    """Return True when a user may read resources owned by target_cohort."""
    return is_same_cohort(user_cohort, target_cohort)


def cohort_of(item: Any) -> str:
    """Extract the cohort from a chunk object or a raw dictionary.

    Objects are read through their ``cohort`` attribute. Dictionaries are read
    through their top-level cohort key, then through a nested ``metadata``
    dictionary. Anything without a recognisable cohort yields "".
    """
    if not isinstance(item, dict):
        return normalize_cohort(getattr(item, "cohort", None))

    for key in _COHORT_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_cohort(value)

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in _COHORT_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return normalize_cohort(value)

    return ""


def scope_by_cohort(items: list[Any], cohort: str | None) -> list[Any]:
    """Keep only the items owned by the requested cohort.

    Works on both retrieved chunk objects and raw dictionaries. An empty
    cohort returns an empty list, never the full set.
    """
    expected = normalize_cohort(cohort)
    if not expected:
        return []
    return [item for item in items if is_same_cohort(cohort_of(item), expected)]


def find_leaked_items(items: list[Any], cohort: str | None) -> list[Any]:
    """Return the items that do NOT belong to the requested cohort.

    The inverse of :func:`scope_by_cohort`, used by the evaluation suite to
    report exactly which records leaked.
    """
    expected = normalize_cohort(cohort)
    return [item for item in items if not is_same_cohort(cohort_of(item), expected)]
