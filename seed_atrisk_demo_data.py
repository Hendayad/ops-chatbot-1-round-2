"""One-off script to seed a few days of at-risk state for a dashboard demo.

Run this AFTER `uv run alembic upgrade head` and with the db container up.
It fabricates LearnerProgress snapshots, runs the real detector against
them, and persists results via the real app.atrisk.state module — so the
data the dashboard shows is produced by the same code path the scheduled
job uses, not a fake shortcut.

Usage:
    uv run python seed_atrisk_demo_data.py

Safe to re-run: upsert_at_risk_state upserts by (learner_id, run_date), so
running this twice for the same day just overwrites that day's rows.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import OperationalError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.atrisk.detector import run_detector
from app.atrisk.state import upsert_at_risk_state

# Merging main added User.notification_preference, a relationship declared
# by string name ("NotificationPreference"). SQLAlchemy can't resolve that
# name unless the class has actually been imported somewhere -- without this,
# mapper configuration fails with InvalidRequestError the first time any
# query touches the User/AtRiskStateRecord mappers.
from app.models.notification_preference import NotificationPreference  # noqa: F401
from app.services.database import database_service
from app.schemas.progress import FeedbackEntry, LearnerProgress

random.seed(7)  # reproducible demo data

NUM_LEARNERS = 120
NUM_DAYS = 14  # trailing days of history, so the trend chart has a shape


def _make_learner(learner_id: str, as_of: datetime, risk_bias: float) -> LearnerProgress:
    """Build one plausible snapshot; risk_bias in [0,1] skews it toward at-risk."""
    total_tasks = random.randint(8, 20)
    completed_tasks = int(total_tasks * random.uniform(0.1, 1.0) * (1 - risk_bias * 0.6))
    completed_tasks = min(completed_tasks, total_tasks)

    missed_deadlines = random.randint(0, 4) if random.random() < risk_bias else random.randint(0, 1)

    inactive_days = random.uniform(0, 14) if random.random() < risk_bias else random.uniform(0, 3)
    last_active_at = as_of - timedelta(days=inactive_days)

    feedback = []
    if random.random() < 0.7:
        score = random.uniform(1.0, 3.0) if random.random() < risk_bias else random.uniform(3.0, 5.0)
        feedback.append(FeedbackEntry(score=round(score, 1), submitted_at=as_of - timedelta(days=1)))

    return LearnerProgress(
        learner_id=learner_id,
        cohort_id="cohort_demo",
        as_of=as_of,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        missed_deadlines=missed_deadlines,
        last_active_at=last_active_at,
        recent_feedback=feedback,
    )


@retry(
    retry=retry_if_exception_type(OperationalError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    reraise=True,
)
def _upsert_with_retry(result, run_date):
    """Persist one learner's result, retrying transient pooler drops.

    A free-tier/shared connection pooler (e.g. Supabase's Session pooler)
    can reset an in-flight connection under load even when the app's own
    pool settings are conservative. On failure, dispose the shared engine
    so the pool's stale connection records are dropped and the next
    attempt opens a genuinely fresh connection, then retry with backoff
    instead of losing the whole ~1,680-call run to one blip.
    """
    try:
        upsert_at_risk_state(result, run_date=run_date)
    except OperationalError:
        database_service.engine.dispose()
        raise


def main() -> None:
    today = datetime.now(UTC).date()
    for day_offset in range(NUM_DAYS - 1, -1, -1):
        run_date = today - timedelta(days=day_offset)
        as_of = datetime.combine(run_date, datetime.min.time(), tzinfo=UTC)

        # Trend upward slightly toward today, just so the chart has a shape.
        base_risk = 0.18 + (0.12 * (NUM_DAYS - 1 - day_offset) / max(1, NUM_DAYS - 1))

        snapshots = [
            _make_learner(f"learner_{i:04d}", as_of, risk_bias=base_risk)
            for i in range(NUM_LEARNERS)
        ]
        results = run_detector(snapshots)
        for result in results:
            _upsert_with_retry(result, run_date=run_date)

        at_risk_count = sum(1 for r in results if r.signals.at_risk)
        print(f"{run_date}: {at_risk_count}/{NUM_LEARNERS} at risk")

    print("Done. Refresh the dashboard.")


if __name__ == "__main__":
    main()
