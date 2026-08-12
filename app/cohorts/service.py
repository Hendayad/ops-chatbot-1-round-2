"""Database-backed cohort lifecycle and access helpers."""

from __future__ import annotations

from sqlalchemy import text

from app.cohorts.scope import normalize_cohort
from app.services.database import database_service

UNASSIGNED_COHORT_ID = "unassigned"

db_service = database_service


def sync_expired_cohorts() -> int:
    """Disable cohorts whose end date has passed and return rows changed."""
    with db_service.get_session_maker() as session:
        result = session.execute(
            text(
                """
                UPDATE cohort
                SET enabled = FALSE
                WHERE enabled = TRUE
                  AND end_date IS NOT NULL
                  AND end_date < CURRENT_DATE
                """
            )
        )
        session.commit()
        return int(result.rowcount or 0)


def is_servable_cohort(cohort_id: str | None) -> bool:
    """Return whether a cohort currently exists and may serve KB answers."""
    normalized = normalize_cohort(cohort_id)

    if not normalized or normalized == UNASSIGNED_COHORT_ID:
        return False

    sync_expired_cohorts()

    with db_service.get_session_maker() as session:
        row = session.execute(
            text(
                """
                SELECT 1
                FROM cohort
                WHERE LOWER(cohort_id) = :cohort_id
                  AND enabled = TRUE
                  AND (
                      end_date IS NULL
                      OR end_date >= CURRENT_DATE
                  )
                LIMIT 1
                """
            ),
            {"cohort_id": normalized},
        ).first()

    return row is not None