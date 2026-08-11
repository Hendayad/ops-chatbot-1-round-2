"""Authorized, rate-limited read-only APIs for at-risk Ops dashboards (PRD F3.3).

Mirrors the pattern in app.api.v1.tickets: authentication via get_current_user,
per-endpoint rate limiting, and all persistence/business logic staying inside
app.atrisk.state rather than being re-implemented here. This router only
translates that module's read functions into HTTP responses.

Authorization: every endpoint requires get_current_ops_user (User.is_ops),
not just get_current_user -- these are Ops-facing endpoints exposing every
flagged learner_id for a cohort, not something any authenticated account
should be able to call. Every query is also scoped by a required cohort_id
so one Ops user's request can never combine another cohort's data into the
response (see app.atrisk.state's cohort_id docstrings for the full reasoning).
"""

from datetime import date, timedelta
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.v1.auth import get_current_ops_user
from app.atrisk.state import (
    AtRiskAggregate,
    get_aggregate,
    get_aggregate_trend,
    get_at_risk_learner_ids,
    get_latest_run_date,
)
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.user import User
from app.schemas.base import BaseResponse

router = APIRouter()

# Same fallback pattern as tickets.py: works even before an atrisk-specific
# RATE_LIMIT_ATRISK env var / Settings default exists.
_ATRISK_RATE_LIMIT = settings.RATE_LIMIT_ENDPOINTS.get("atrisk", ["60 per minute"])[0]


class AtRiskSummaryResponse(BaseResponse):
    """Today's (or latest available) at-risk aggregate, for the Ops dashboard's top tiles."""

    aggregate: AtRiskAggregate


class AtRiskTrendResponse(BaseResponse):
    """Day-by-day at-risk aggregates over a window, for the Ops dashboard's trend chart."""

    start_date: date
    end_date: date
    trend: list[AtRiskAggregate]


class AtRiskLearnersResponse(BaseResponse):
    """Learner IDs currently flagged at_risk, for the Ops dashboard's learner list."""

    run_date: date | None
    learner_ids: list[str]
    count: int


def _raise_http_error(exc: Exception, *, operation: str) -> NoReturn:
    """Translate unexpected failures without exposing internal details, matching tickets.py."""
    logger.exception(
        "ops_atrisk_api_failed",
        operation=operation,
        error_type=type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="At-risk data is temporarily unavailable",
    )


@router.get("/summary", response_model=AtRiskSummaryResponse)
@limiter.limit(_ATRISK_RATE_LIMIT)
async def get_atrisk_summary(
    request: Request,
    cohort_id: str = Query(..., description="Cohort to scope this summary to."),
    run_date: date | None = Query(default=None, description="Defaults to the latest available run_date."),
    current_user: User = Depends(get_current_ops_user),
) -> AtRiskSummaryResponse:
    """Return the at-risk aggregate (counts + per-reason breakdown) for one day, for one cohort.

    Backs the Ops dashboard's top-of-page KPI tiles: total learners evaluated,
    how many are at_risk, and the percent, plus a breakdown by which signal
    tripped (missed_deadlines / inactive / low_progress / low_feedback).
    """
    try:
        aggregate = get_aggregate(run_date, cohort_id=cohort_id)
        logger.info(
            "ops_atrisk_summary_viewed",
            authenticated_user_id=current_user.id,
            cohort_id=cohort_id,
            run_date=str(aggregate.run_date),
            at_risk_count=aggregate.at_risk_count,
        )
        return AtRiskSummaryResponse(aggregate=aggregate)
    except Exception as exc:
        _raise_http_error(exc, operation="summary")


@router.get("/trend", response_model=AtRiskTrendResponse)
@limiter.limit(_ATRISK_RATE_LIMIT)
async def get_atrisk_trend(
    request: Request,
    cohort_id: str = Query(..., description="Cohort to scope this trend to."),
    days: int = Query(
        default=14, ge=1, le=90,
        description="Window size in days, ending today (UTC). Ignored when start_date/end_date are both given.",
    ),
    start_date: date | None = Query(default=None, description="Explicit range start. Requires end_date."),
    end_date: date | None = Query(default=None, description="Explicit range end. Requires start_date."),
    current_user: User = Depends(get_current_ops_user),
) -> AtRiskTrendResponse:
    """Return one at-risk aggregate per day for a date range, for one cohort.

    Backs the Ops dashboard's trend chart. Pass an explicit `start_date` +
    `end_date` for a specific range, or omit both to fall back to the
    trailing `days` days ending on the cohort's latest run date. Gap days
    with no persisted state are zero-filled by
    app.atrisk.state.get_aggregate_trend, so the chart never has to
    special-case a missing day.
    """
    try:
        if start_date and end_date:
            if start_date > end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date must be on or before end_date.",
                )
            if (end_date - start_date).days > 90:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Date range cannot exceed 90 days.",
                )
        else:
            end_date = get_latest_run_date(cohort_id=cohort_id) or date.today()
            start_date = end_date - timedelta(days=days - 1)
        trend = get_aggregate_trend(start_date, end_date, cohort_id=cohort_id)
        logger.info(
            "ops_atrisk_trend_viewed",
            authenticated_user_id=current_user.id,
            cohort_id=cohort_id,
            start_date=str(start_date),
            end_date=str(end_date),
        )
        return AtRiskTrendResponse(start_date=start_date, end_date=end_date, trend=trend)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_http_error(exc, operation="trend")


@router.get("/learners", response_model=AtRiskLearnersResponse)
@limiter.limit(_ATRISK_RATE_LIMIT)
async def get_atrisk_learners(
    request: Request,
    cohort_id: str = Query(..., description="Cohort to scope this learner list to."),
    run_date: date | None = Query(default=None, description="Defaults to the latest available run_date."),
    current_user: User = Depends(get_current_ops_user),
) -> AtRiskLearnersResponse:
    """Return the learner_ids currently flagged at_risk for one day, for one cohort.

    Backs the Ops dashboard's learner list. This intentionally returns only
    learner_id (no PII beyond that) — the dashboard is expected to resolve
    display names client-side or via whatever learner-lookup endpoint the
    platform team already exposes, not duplicate that data here.
    """
    try:
        target_date = run_date or get_latest_run_date(cohort_id=cohort_id)
        learner_ids = get_at_risk_learner_ids(target_date, cohort_id=cohort_id)
        logger.info(
            "ops_atrisk_learners_viewed",
            authenticated_user_id=current_user.id,
            cohort_id=cohort_id,
            run_date=str(target_date) if target_date else None,
            count=len(learner_ids),
        )
        return AtRiskLearnersResponse(run_date=target_date, learner_ids=learner_ids, count=len(learner_ids))
    except Exception as exc:
        _raise_http_error(exc, operation="learners")
