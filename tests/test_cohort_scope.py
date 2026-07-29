from app.cohorts.scope import scope_retrieval_by_cohort

def test_cohort_isolation():
    docs = [{"id": 1, "cohort_id": "A"}, {"id": 2, "cohort_id": "B"}]
    res = scope_retrieval_by_cohort("test", "A", docs)
    assert len(res) == 1
    assert res[0]["cohort_id"] == "A"
