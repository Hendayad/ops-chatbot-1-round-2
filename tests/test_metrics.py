from app.dashboards.aggregate import aggregate_open_issues, build_alerts


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
