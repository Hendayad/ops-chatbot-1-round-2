import json
import os
from typing import Dict, Any

class CohortConfigLoader:
    def __init__(self, config_path: str = "cohorts_config.json"):
        self.config_path = config_path

    def load_cohort_config(self, cohort_id: str) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {"cohort_id": cohort_id, "materials": []}
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(cohort_id, {"cohort_id": cohort_id, "materials": []})
