from app.dashboards.aggregate import aggregate_open_issues


def test_aggregate_open_issues():
    m03 = [{"id": 1, "status": "open", "severity": "low"}]
    m08 = [{"id": 2, "status": "at_risk", "severity": "high"}]
    res = aggregate_open_issues(m03, m08)
    assert res["total_open"] == 2
    assert res["at_risk_count"] == 1
