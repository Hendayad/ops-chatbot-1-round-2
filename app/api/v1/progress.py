"""Ops-gated ingestion API for real learner-progress snapshots (PRD F2.3).

app.atrisk.progress_store already has the persisted table and both the
write side (upsert_learner_progress) and read side
(list_all_learner_progress, which doubles as the at-risk job's
ProgressProvider). What was missing was any real caller of the write
side -- until an ingestion path calls it, the table stays empty and the
at-risk job correctly evaluates zero learners.

This intentionally is NOT an LMS sync or any other real integration --
there isn't one to build against yet (see progress_store.py's module
docstring: no upstream system exists in this codebase or any teammate's
branch to import from). It's the simplest thing that lets the pipeline
be exercised end to end with real rows: a batch upsert endpoint an Ops
user (or a future scheduled importer acting on their behalf) can call
with however many LearnerProgress snapshots they have on hand -- a CSV
load, a manual entry, a one-off backfill.

Mirrors app.api.v1.atrisk's pattern: Ops-only auth via
get_current_ops_user, per-endpoint rate limiting, and all persistence
logic staying inside app.atrisk.progress_store rather than being
reimplemented here.
"""

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_ops_user
from app.atrisk.progress_store import upsert_learner_progress
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.user import User
from app.schemas.base import BaseResponse
from app.schemas.progress import LearnerProgress

router = APIRouter()

# Same fallback pattern as atrisk.py: works even before a progress-specific
# RATE_LIMIT_PROGRESS env var / Settings default exists.
_PROGRESS_RATE_LIMIT = settings.RATE_LIMIT_ENDPOINTS.get("progress", ["30 per minute"])[0]


class ProgressBatchRequest(BaseModel):
    """One or more learner-progress snapshots to persist."""

    snapshots: list[LearnerProgress] = Field(
        ..., min_length=1, max_length=500, description="Snapshots to upsert, one per learner."
    )


class ProgressBatchResponse(BaseResponse):
    """Result of a batch upsert -- how many snapshots landed, and for whom."""

    upserted_count: int
    learner_ids: list[str]


def _raise_http_error(exc: Exception, *, operation: str) -> NoReturn:
    """Translate unexpected failures without exposing internal details, matching atrisk.py."""
    logger.exception(
        "ops_progress_api_failed",
        operation=operation,
        error_type=type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Progress ingestion is temporarily unavailable",
    )


@router.post("/batch", response_model=ProgressBatchResponse)
@limiter.limit(_PROGRESS_RATE_LIMIT)
async def ingest_progress_batch(
    request: Request,
    body: ProgressBatchRequest,
    current_user: User = Depends(get_current_ops_user),
) -> ProgressBatchResponse:
    """Upsert a batch of learner-progress snapshots (PRD F2.3's ingestion path).

    Each snapshot replaces that learner's prior row (see
    upsert_learner_progress's docstring -- this table is latest-snapshot-
    per-learner, not a history log). Safe to call repeatedly with
    overlapping learner_ids; last write wins per learner.

    Args:
        request: The FastAPI request object for rate limiting.
        body: The batch of snapshots to persist.
        current_user: The authenticated Ops user performing this ingestion.

    Returns:
        ProgressBatchResponse: How many snapshots were upserted, and for which learners.
    """
    try:
        learner_ids: list[str] = []
        for snapshot in body.snapshots:
            record = upsert_learner_progress(snapshot)
            learner_ids.append(record.learner_id)

        logger.info(
            "ops_progress_batch_ingested",
            authenticated_user_id=current_user.id,
            upserted_count=len(learner_ids),
            learner_ids=learner_ids,
        )
        return ProgressBatchResponse(upserted_count=len(learner_ids), learner_ids=learner_ids)
    except Exception as exc:
        _raise_http_error(exc, operation="ingest_batch")
