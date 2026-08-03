"""Tests for the M09 Ops metrics: aggregation, alerts, and instrumentation.

The aggregation tests check the maths. The instrumentation tests check that the
runtime paths actually write to the metrics, because a metric that is defined
but never recorded looks healthy on /metrics and is empty in Grafana.
"""

import json
import pathlib
import re

import pytest
from prometheus_client import REGISTRY

from app.dashboards.aggregate import aggregate_open_issues, build_alerts
from app.risk.signals import AtRiskSignal

from app.dashboards.metrics import get_at_risk_snapshot, risk_level_for
from app.metrics.kpis import (
    ACTIVE_ALERTS,
    ALERT_TYPES,
    AT_RISK_ISSUES,
    CONNECTOR_SYNC_FAILURES,
    DEFLECTION_RATE,
    FIRST_RESPONSE_TIME,
    update_alert_metrics,
    update_at_risk_metrics,
)
from app.risk.signals import RiskIndicator
from app.schemas.progress import LearnerProgress


DASHBOARD_PATH = pathlib.Path(__file__).resolve().parents[1] / "dashboards" / "grafana.json"


def _alert_value(alert_type):
    """Read the current 1/0 value of one alert series."""
    return ACTIVE_ALERTS.labels(alert_type=alert_type)._value.get()


# --- Open issues aggregation ---


def test_aggregate_open_issues_counts_open_and_in_progress():
    m03 = [{"id": 1, "status": "open"}, {"id": 2, "status": "resolved"}]
    m08 = [{"id": 3, "status": "in_progress"}]
    res = aggregate_open_issues(m03, m08)
    assert res["total_open"] == 2
    assert res["total_issues"] == 3


def test_aggregate_open_issues_excludes_closed_and_resolved():
    m03 = [{"id": 1, "status": "resolved"}, {"id": 2, "status": "closed"}]
    res = aggregate_open_issues(m03, [])
    assert res["total_open"] == 0
    assert res["total_issues"] == 2


# --- Alerts ---


def test_build_alerts_flags_high_escalation_rate():
    alerts = build_alerts(escalation_rate=0.9, resolution_time=[], total_open=0)
    assert any(a["type"] == "high_escalation_rate" for a in alerts)


def test_build_alerts_flags_slow_resolution():
    resolution_time = [{"ticket_id": "t1", "estimated_resolution_seconds": 100000}]
    alerts = build_alerts(escalation_rate=0.0, resolution_time=resolution_time, total_open=0)
    assert any(a["type"] == "slow_resolution" for a in alerts)


def test_build_alerts_flags_open_issues_backlog():
    alerts = build_alerts(escalation_rate=0.0, resolution_time=[], total_open=25)
    assert any(a["type"] == "open_issues_backlog" for a in alerts)


def test_build_alerts_empty_when_all_healthy():
    alerts = build_alerts(escalation_rate=0.1, resolution_time=[], total_open=1)
    assert alerts == []


def test_update_alert_metrics_marks_firing_alert():
    update_alert_metrics([{"type": "high_escalation_rate", "message": "x"}])

    assert _alert_value("high_escalation_rate") == 1


def test_update_alert_metrics_clears_alerts_that_stopped_firing():
    """A gauge keeps its last value, so cleared alerts must be written as 0."""
    update_alert_metrics([{"type": "high_escalation_rate", "message": "x"}])
    update_alert_metrics([])

    assert _alert_value("high_escalation_rate") == 0


def test_update_alert_metrics_writes_every_known_type():
    update_alert_metrics([])

    for alert_type in ALERT_TYPES:
        assert _alert_value(alert_type) == 0


# --- At-risk snapshot, computed through the M05 contract ---


def _progress(learner_id: str, cohort_id: str, **overrides) -> LearnerProgress:
    """Build a healthy learner, overridden field by field to trigger indicators."""
    values = {
        "learner_id": learner_id,
        "cohort_id": cohort_id,
        "total_tasks": 10,
        "completed_tasks": 10,
        "missed_deadlines": 0,
    }
    values.update(overrides)
    return LearnerProgress(**values)


def test_at_risk_snapshot_is_empty_without_progress_data():
    snapshot = get_at_risk_snapshot()
    assert snapshot == {"at_risk_count": 0, "by_risk_level": {}, "by_cohort": {}}


def test_at_risk_snapshot_excludes_healthy_learners():
    snapshot = get_at_risk_snapshot([_progress("l1", "cohort-a")])
    assert snapshot["at_risk_count"] == 0


def test_at_risk_snapshot_counts_learners_flagged_by_m05():
    """One missed-deadline breach is a single indicator, so risk level is low."""
    snapshot = get_at_risk_snapshot([_progress("l1", "cohort-a", missed_deadlines=5)])

    assert snapshot["at_risk_count"] == 1
    assert snapshot["by_risk_level"] == {"low": 1}
    assert snapshot["by_cohort"] == {"cohort-a": {"low": 1}}


def test_at_risk_snapshot_separates_cohorts():
    snapshot = get_at_risk_snapshot(
        [
            _progress("l1", "cohort-a", missed_deadlines=5),
            _progress("l2", "cohort-b", missed_deadlines=5),
        ]
    )

    assert snapshot["by_cohort"] == {"cohort-a": {"low": 1}, "cohort-b": {"low": 1}}

@pytest.mark.parametrize(
    "indicator_count, expected_level",
    [(1, "low"), (2, "medium"), (3, "high"), (4, "high")],
)
def test_risk_level_grades_by_indicator_count(
    indicator_count: int,
    expected_level: str,
) -> None:
    signal = AtRiskSignal(
        learner_id="learner-1",
        cohort_id="cohort-1",
        triggered_indicators=list(RiskIndicator)[:indicator_count],
        is_at_risk=indicator_count > 0,
    )

    assert risk_level_for(signal) == expected_level

def test_update_at_risk_metrics_publishes_per_cohort_gauge():
    update_at_risk_metrics({"by_cohort": {"cohort-a": {"high": 3}}})

    assert AT_RISK_ISSUES.labels(cohort="cohort-a", risk_level="high")._value.get() == 3


# --- Instrumentation: every metric has a runtime writer ---


def test_answer_node_records_first_response_time(monkeypatch):
    """Even a refusal is a first response, so the histogram must be observed."""
    import asyncio

    from app.graph.nodes import answer as answer_module

    before = FIRST_RESPONSE_TIME.labels(cohort="cohort-a")._sum.get()
    state = {"messages": [{"role": "user", "content": "when is the deadline"}], "cohort": "cohort-a"}
    monkeypatch.setattr(
        answer_module,
        "generate_grounded_answer",
        lambda question, *, cohort: _refusal_outcome(),
    )

    asyncio.run(answer_module.grounded_answer(state))

    assert FIRST_RESPONSE_TIME.labels(cohort="cohort-a")._sum.get() >= before


def test_answer_node_counts_a_grounded_answer_as_deflected(monkeypatch):
    import asyncio

    from app.graph.nodes import answer as answer_module

    before = DEFLECTION_RATE.labels(cohort="cohort-a")._value.get()
    state = {"messages": [{"role": "user", "content": "when is the deadline"}], "cohort": "cohort-a"}
    monkeypatch.setattr(
        answer_module,
        "generate_grounded_answer",
        lambda question, *, cohort: _grounded_outcome(),
    )

    asyncio.run(answer_module.grounded_answer(state))

    assert DEFLECTION_RATE.labels(cohort="cohort-a")._value.get() == before + 1


def test_answer_node_does_not_count_a_refusal_as_deflected(monkeypatch):
    import asyncio

    from app.graph.nodes import answer as answer_module

    before = DEFLECTION_RATE.labels(cohort="cohort-a")._value.get()
    state = {"messages": [{"role": "user", "content": "when is the deadline"}], "cohort": "cohort-a"}
    monkeypatch.setattr(
        answer_module,
        "generate_grounded_answer",
        lambda question, *, cohort: _refusal_outcome(),
    )

    asyncio.run(answer_module.grounded_answer(state))

    assert DEFLECTION_RATE.labels(cohort="cohort-a")._value.get() == before


async def _grounded_outcome():
    """A successful grounded answer, as the node's generator would return it."""
    from app.graph.nodes.answer import AnswerOutcome

    return AnswerOutcome(answer="The deadline is Friday.", grounded=True, needs_escalation=False)


async def _refusal_outcome():
    """An honest refusal, as the node's generator would return it."""
    from app.graph.nodes.answer import AnswerOutcome

    return AnswerOutcome(answer="I cannot answer that.", grounded=False, needs_escalation=True)


def test_failed_ops_notification_records_a_connector_failure():
    """Storing a ticket but failing to tell Ops is a connector sync failure."""
    import asyncio
    from datetime import datetime, timezone

    from app.models.escalation_ticket import EscalationTicket
    from app.tickets.service import TicketService

    class BrokenNotifier:
        def notify_ticket_created(self, notification):
            raise RuntimeError("channel unreachable")

    service = TicketService(notifier=BrokenNotifier())

    ticket = EscalationTicket(
    id="esc_test",
    source="answering",
    reason="knowledge_gap",  # <-- add this
    status="open",
    problem="p",
    what_was_tried="w",
    context="c",
    suggested_next_step="s",
    summary="summary",
    user_goal="goal",
    key_facts=[],
    assistant_actions=[],
    open_questions=[],
    privacy_note="No transcript stored.",
    session_id=None,
    user_id=None,
    created_at=datetime.now(timezone.utc),
)

    before = CONNECTOR_SYNC_FAILURES.labels(
        connector_name="BrokenNotifier"
    )._value.get()

    delivered = asyncio.run(service._notify_ops(ticket))

    assert delivered is False
    assert (
        CONNECTOR_SYNC_FAILURES.labels(
            connector_name="BrokenNotifier"
        )._value.get()
        == before + 1
    )
# --- The dashboard may only query metrics this application defines ---


def test_grafana_dashboard_is_valid_json():
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    assert dashboard["panels"], "the dashboard must contain at least one panel"


def test_grafana_dashboard_queries_only_defined_metrics():
    """A panel querying a name nothing publishes renders as 'No data' forever."""
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    referenced = set(re.findall(r"ops_[a-z0-9_]+", json.dumps(dashboard)))

    assert referenced, "no ops_* metric found in the dashboard"
    undefined = sorted(name for name in referenced if name not in REGISTRY._names_to_collectors)
    assert not undefined, f"dashboard queries metrics that are never published: {undefined}"


def test_every_panel_has_a_title_and_a_query():
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    for panel in dashboard["panels"]:
        assert panel.get("title"), f"panel {panel.get('id')} has no title"
        assert panel.get("targets"), f"panel {panel['title']} has no query"


# --- M08 connector seam ---


def test_connector_issues_are_empty_without_a_registered_source():
    from app.dashboards.aggregate import get_connector_issues, set_connector_source

    set_connector_source(None)
    assert get_connector_issues() == []


def test_registered_connector_issues_reach_the_aggregate():
    from app.dashboards.aggregate import get_connector_issues, set_connector_source

    set_connector_source(lambda: [{"id": "ext-1", "status": "open"}])
    try:
        combined = aggregate_open_issues([{"id": 1, "status": "open"}], get_connector_issues())
        assert combined["total_open"] == 2
        assert combined["total_issues"] == 2
    finally:
        set_connector_source(None)


def test_a_broken_connector_does_not_blank_the_dashboard():
    """Internal tickets must still render when the external connector fails."""
    from app.dashboards.aggregate import get_connector_issues, set_connector_source

    def broken():
        raise RuntimeError("connector unreachable")

    set_connector_source(broken)
    try:
        combined = aggregate_open_issues([{"id": 1, "status": "open"}], get_connector_issues())
        assert combined["total_open"] == 1
    finally:
        set_connector_source(None)
