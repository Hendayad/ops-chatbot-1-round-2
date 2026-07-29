from app.cohorts.scope import scope_retrieval_by_cohort

def evaluate_zero_leakage():
    docs = [
        {"id": 1, "cohort_id": "cohort_a", "content": "Secret A"},
        {"id": 2, "cohort_id": "cohort_b", "content": "Secret B"},
    ]
    results_a = scope_retrieval_by_cohort("query", "cohort_a", docs)
    leakage = [d for d in results_a if d["cohort_id"] != "cohort_a"]
    assert len(leakage) == 0, "Cross-cohort answer leakage detected!"
    print("Zero leakage evaluation PASSED successfully.")

if __name__ == "__main__":
    evaluate_zero_leakage()
