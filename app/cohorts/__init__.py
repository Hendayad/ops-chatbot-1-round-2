"""Multi-cohort support (M10 / F3.4): isolation rules and cohort configuration.

Isolation has two halves and both are exported here:

* ``scope`` answers "does this item belong to that cohort?"
* ``config`` answers "does that cohort exist at all?"

Both fail closed — an absent cohort matches nothing and is served nothing.
"""

from app.cohorts.config import (
    CohortConfigLoader,
    cohort_config,
    cohort_gating_enabled,
    is_servable_cohort,
)
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
    "cohort_config",
    "cohort_gating_enabled",
    "cohort_of",
    "find_leaked_items",
    "is_same_cohort",
    "is_servable_cohort",
    "normalize_cohort",
    "scope_by_cohort",
    "validate_cohort_access",
]
