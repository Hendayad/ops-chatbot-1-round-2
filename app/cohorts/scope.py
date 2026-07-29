from typing import List, Dict, Any

def scope_retrieval_by_cohort(query: str, cohort_id: str, all_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [doc for doc in all_documents if doc.get("cohort_id") == cohort_id]
