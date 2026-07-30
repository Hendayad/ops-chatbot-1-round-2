"""Multi-cohort support (M10 / F3.4): isolation rules and cohort configuration."""

from app.cohorts.config import CohortConfigLoader
from app.cohorts.scope import (
    cohort_of,
    find_leaked_items,
    is_same_cohort,
    normalize_cohort,
    scope_by_cohort,
    validate_cohort_access,
)

__all__ = [
    "CohortConfigLoader",
    "cohort_of",
    "find_leaked_items",
    "is_same_cohort",
    "normalize_cohort",
    "scope_by_cohort",
    "validate_cohort_access",
]
