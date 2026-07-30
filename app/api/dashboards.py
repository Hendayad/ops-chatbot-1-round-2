"""Ops Console dashboard API — read-only support metrics for program leads."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from app.observability.kpis import update_alert_metrics, update_open_issues_metrics, update_support_metrics
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.dashboards.aggregate import aggregate_open_issues, build_alerts
from app.dashboards.metrics import get_support_metrics
from app.models.user import User
from app.services.database import DatabaseService
from app.tickets.service import list_tickets as list_open_tickets

router = APIRouter()
db_service = DatabaseService()

_MAX_TICKETS_FOR_DASHBOARD = 100


@router.get("/metrics")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["dashboards"][0])
async def get_dashboard_metrics(
    request: Request,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    user: User = Depends(get_current_user),
):
    """Return the full Ops dashboard payload for the given time window (M09 / F3.3).

    If start/end are omitted, defaults to the last 7 days.

    Args:
        request: The FastAPI request object for rate limiting.
        start: Start of the reporting window (optional, defaults to 7 days before end).
        end: End of the reporting window (optional, defaults to now).
        user: The authenticated user requesting the metrics.

    Returns:
        dict: support_volume, escalation_rate, resolution_time (estimate),
        at_risk, open_issues, and alerts.
    """
    try:
        resolved_end = end or datetime.now(timezone.utc)
        resolved_start = start or (resolved_end - timedelta(days=7))

        with db_service.get_session_maker() as session:
            metrics = get_support_metrics(session, resolved_start, resolved_end)
        update_support_metrics(metrics)

        # NOTE: only the first page of tickets is considered for the open-issues
        # count. Good enough for a dashboard summary; a full backlog view would
        # need real pagination.
        tickets = await list_open_tickets(limit=_MAX_TICKETS_FOR_DASHBOARD)
        ticket_dicts = [{"status": ticket.status} for ticket in tickets]
        # M08 (ticketing integration) is not implemented yet, so there are no
        # external connector issues to include here.
        open_issues = aggregate_open_issues(ticket_dicts, connector_issues=[])
        update_open_issues_metrics(open_issues)

        alerts = build_alerts(
            escalation_rate=metrics["escalation_rate"],
            resolution_time=metrics["resolution_time"],
            total_open=open_issues["total_open"],
        )
        update_alert_metrics(alerts)

        return {**metrics, "open_issues": open_issues, "alerts": alerts}
    except Exception as e:
        logger.exception("dashboard_metrics_failed", user_id=user.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

