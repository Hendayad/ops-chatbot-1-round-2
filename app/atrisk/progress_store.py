"""Persistence layer for real learner-progress data -- the ProgressProvider source (PRD F2.3).

Until now, app.jobs.atrisk_job.run_at_risk_job's ``progress_provider`` had
nothing real to inject: no table, no ingestion path, nothing in this
codebase (or any teammate's branch) computes actual learner progress. This
module is that missing piece -- a real, persisted, queryable source of
LearnerProgress snapshots.

What this does NOT solve: where the numbers in a snapshot actually come
from. Nothing here knows about real tasks, deadlines, or feedback --
that's a genuine open question (is there an LMS? a spreadsheet? a manual
process?) that depends on systems outside this codebase. What this module
gives that answer, whenever it arrives, is somewhere real to land:
``upsert_learner_progress`` is the write side any future ingestion job
(an LMS sync, a CSV importer, a manual admin action) should call, and
``list_all_learner_progress`` -- which doubles as the real
``ProgressProvider`` callable -- is the read side the scheduled job
already knows how to consume. Until something calls the write side, this
table is empty and the at-risk job correctly evaluates zero learners,
exactly as it does today.

Follows the same reserve-then-commit-via-shared-singleton pattern as
app/atrisk/state.py: a fresh Session per call against the app's shared
`database_service` singleton, not a fresh DatabaseService()/engine per
call -- see that module's docstring for why a fresh engine per call is
dangerous against a connection-capped pooler (e.g. Supabase's Session
pooler).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlmodel import Field, UniqueConstraint, select

from app.models.base import BaseModel as ORMBaseModel
from app.schemas.progress import FeedbackEntry, LearnerProgress
from app.services.database import database_service


class LearnerProgressRecord(ORMBaseModel, table=True):
    """Latest known progress snapshot for one learner.

    One row per learner_id (upserted in place), not a history log --
    nothing in this codebase has an actual ingestion pipeline yet that
    would make a time series meaningful. Whatever eventually ingests real
    progress data is expected to call upsert_learner_progress with a
    fresh snapshot each time it runs; this table always reflects the most
    recent snapshot per learner.

    Attributes:
        id: Primary key.
        learner_id: The learner this record is for. Unique per row (see above).
        cohort_id: The learner's cohort at snapshot time.
        as_of: UTC timestamp this snapshot was computed/ingested at.
        total_tasks: Total tasks assigned to the learner so far.
        completed_tasks: Tasks the learner has completed.
        missed_deadlines: Count of task/project deadlines missed to date.
        last_active_at: UTC timestamp of the learner's last recorded
            activity, if any.
        recent_feedback_json: JSON-encoded list of {"score", "submitted_at"}
            objects -- see app.schemas.progress.FeedbackEntry. Stored as a
            JSON blob (mirroring what LearnerProgress expects) rather than
            a normalized child table, since there's no real feedback
            source yet to justify one.
        created_at: Inherited from BaseModel -- when this row was first written.
    """

    __table_args__ = (UniqueConstraint("learner_id", name="uq_learnerprogressrecord_learner_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    learner_id: str = Field(index=True)
    cohort_id: str = Field(index=True)
    as_of: datetime
    total_tasks: int
    completed_tasks: int
    missed_deadlines: int = Field(default=0)
    last_active_at: Optional[datetime] = Field(default=None)
    recent_feedback_json: str = Field(default="[]")


def _to_schema(record: LearnerProgressRecord) -> LearnerProgress:
    """Convert a persisted record back into the LearnerProgress the detector expects."""
    feedback_raw = json.loads(record.recent_feedback_json)
    return LearnerProgress(
        learner_id=record.learner_id,
        cohort_id=record.cohort_id,
        as_of=record.as_of,
        total_tasks=record.total_tasks,
        completed_tasks=record.completed_tasks,
        missed_deadlines=record.missed_deadlines,
        last_active_at=record.last_active_at,
        recent_feedback=[FeedbackEntry(**entry) for entry in feedback_raw],
    )


def upsert_learner_progress(progress: LearnerProgress) -> LearnerProgressRecord:
    """Persist one learner's progress snapshot, replacing any prior snapshot for that learner.

    Idempotent by learner_id: calling this again for the same learner
    overwrites their row with the new snapshot rather than accumulating a
    history (see LearnerProgressRecord's docstring for why). This is the
    write side any real ingestion source should call.

    Args:
        progress: The snapshot to persist.

    Returns:
        The persisted (inserted or updated) LearnerProgressRecord.
    """
    feedback_json = json.dumps([entry.model_dump(mode="json") for entry in progress.recent_feedback])

    db_service = database_service  # shared singleton -- see module docstring
    with db_service.get_session_maker() as session:
        record = session.exec(
            select(LearnerProgressRecord).where(LearnerProgressRecord.learner_id == progress.learner_id)
        ).first()

        if record is None:
            record = LearnerProgressRecord(
                learner_id=progress.learner_id,
                cohort_id=progress.cohort_id,
                as_of=progress.as_of,
                total_tasks=progress.total_tasks,
                completed_tasks=progress.completed_tasks,
                missed_deadlines=progress.missed_deadlines,
                last_active_at=progress.last_active_at,
                recent_feedback_json=feedback_json,
            )
        else:
            record.cohort_id = progress.cohort_id
            record.as_of = progress.as_of
            record.total_tasks = progress.total_tasks
            record.completed_tasks = progress.completed_tasks
            record.missed_deadlines = progress.missed_deadlines
            record.last_active_at = progress.last_active_at
            record.recent_feedback_json = feedback_json

        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def get_learner_progress(learner_id: str) -> Optional[LearnerProgress]:
    """Return one learner's current progress snapshot, if any."""
    db_service = database_service  # shared singleton -- see module docstring
    with db_service.get_session_maker() as session:
        record = session.exec(
            select(LearnerProgressRecord).where(LearnerProgressRecord.learner_id == learner_id)
        ).first()
        return _to_schema(record) if record else None


def list_all_learner_progress() -> list[LearnerProgress]:
    """Return every learner's current progress snapshot.

    This is the real ProgressProvider: its signature (zero args, returns
    list[LearnerProgress]) already satisfies app.jobs.atrisk_job's
    ProgressProvider Protocol, so it can be passed directly as
    run_at_risk_job's progress_provider argument -- see
    app.jobs.atrisk_job.run_scheduled_at_risk_job, which is what the
    scheduler actually calls.

    Returns an empty list until something calls upsert_learner_progress --
    that's correct, not a bug: it means no real progress data has been
    ingested yet, so there's nothing to evaluate.
    """
    db_service = database_service  # shared singleton -- see module docstring
    with db_service.get_session_maker() as session:
        records = session.exec(select(LearnerProgressRecord)).all()
        return [_to_schema(record) for record in records]
