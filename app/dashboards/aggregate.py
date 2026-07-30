"""Open-issues aggregation and simple threshold alerts for the Ops dashboard (M09)."""

from typing import Any

OPEN_STATUSES = {"open", "in_progress"}

_ESCALATION_RATE_ALERT_THRESHOLD = 0.5
_RESOLUTION_TIME_ALERT_SECONDS = 86400  # 1 day
_OPEN_ISSUES_ALERT_THRESHOLD = 20


def aggregate_open_issues(
    internal_tickets: list[dict[str, Any]],
    connector_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    """Combine internal tickets (M03) and connector issues (M08) into one open-issues view.

    An issue counts as "open" when its status is "open" or "in_progress",
    matching TicketStatus in app.schemas.escalation. Resolved/closed issues
    are excluded from the count.
    """
    all_issues = internal_tickets + connector_issues
    open_issues = [issue for issue in all_issues if issue.get("status") in OPEN_STATUSES]

    return {
        "total_open": len(open_issues),
        "total_issues": len(all_issues),
        "issues": open_issues,
    }


def build_alerts(escalation_rate: float, resolution_time: list[dict[str, Any]], total_open: int) -> list[dict[str, str]]:
    """Derive simple threshold-based alerts from already-computed dashboard metrics.

    No new data collection happens here - each alert is just a flag raised
    when an existing metric crosses a fixed threshold, so a program lead
    can see problems at a glance without reading raw numbers.
    """
    alerts = []

    if escalation_rate > _ESCALATION_RATE_ALERT_THRESHOLD:
        alerts.append(
            {
                "type": "high_escalation_rate",
                "message": f"Escalation rate is {escalation_rate:.0%}, above the "
                f"{_ESCALATION_RATE_ALERT_THRESHOLD:.0%} threshold.",
            }
        )

    slow_tickets = [t for t in resolution_time if t["estimated_resolution_seconds"] > _RESOLUTION_TIME_ALERT_SECONDS]
    if slow_tickets:
        alerts.append(
            {
                "type": "slow_resolution",
                "message": f"{len(slow_tickets)} ticket(s) took longer than 24h to reach escalation.",
            }
        )

    if total_open > _OPEN_ISSUES_ALERT_THRESHOLD:
        alerts.append(
            {
                "type": "open_issues_backlog",
                "message": f"{total_open} open issues, above the {_OPEN_ISSUES_ALERT_THRESHOLD} threshold.",
            }
        )

    return alerts
