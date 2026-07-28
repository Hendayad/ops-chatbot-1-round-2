from typing import Dict, Any, List

def aggregate_open_issues(m03_tickets: List[Dict[str, Any]], m08_connector_issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    all_issues = m03_tickets + m08_connector_issues
    at_risk = [i for i in all_issues if i.get("status") == "at_risk" or i.get("severity") == "high"]
    
    return {
        "total_open": len(all_issues),
        "at_risk_count": len(at_risk),
        "issues": all_issues
    }
