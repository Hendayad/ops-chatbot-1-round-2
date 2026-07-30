"""Configuration-driven cohort onboarding (M10 / F3.4).

A new cohort launches by adding an entry to a JSON config file and supplying
its materials — no code change and no redeploy of the graph. This module reads
that file and answers two questions: which cohorts exist, and what is
configured for one of them.

Expected file shape::

    {
      "cohort-a": {"name": "July 2026 Cohort", "materials": ["docs/faq.md"]},
      "cohort-b": {"name": "Sept 2026 Cohort", "materials": []}
    }
"""

import json
import os
from typing import Any

from app.cohorts.scope import normalize_cohort
from app.core.logging import logger

DEFAULT_CONFIG_PATH = "cohorts_config.json"


class CohortConfigLoader:
    """Read cohort definitions from a JSON configuration file.

    Missing or malformed files are treated as "no cohorts configured" rather
    than raising, so a configuration mistake cannot take the application down.
    """

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH) -> None:
        """Store the path of the cohort configuration file."""
        self.config_path = config_path

    def _read_file(self) -> dict[str, Any]:
        """Return the parsed config file, or an empty dict when unusable."""
        if not os.path.exists(self.config_path):
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as config_file:
                data = json.load(config_file)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("cohort_config_unreadable", path=self.config_path, error=str(exc))
            return {}

        if not isinstance(data, dict):
            logger.warning("cohort_config_not_an_object", path=self.config_path)
            return {}
        return data

    def list_cohorts(self) -> list[str]:
        """Return every configured cohort id, sorted for a stable order."""
        return sorted(self._read_file().keys())

    def is_known_cohort(self, cohort_id: str | None) -> bool:
        """Return True when the cohort exists in the configuration file."""
        normalized = normalize_cohort(cohort_id)
        if not normalized:
            return False
        return normalized in self._read_file()

    def load_cohort_config(self, cohort_id: str) -> dict[str, Any]:
        """Return one cohort's configuration.

        An unknown cohort yields an empty template rather than None, so callers
        can read ``materials`` without a null check.
        """
        normalized = normalize_cohort(cohort_id)
        empty = {"cohort_id": normalized, "name": "", "materials": []}
        if not normalized:
            return empty

        entry = self._read_file().get(normalized)
        if not isinstance(entry, dict):
            return empty

        return {
            "cohort_id": normalized,
            "name": entry.get("name", ""),
            "materials": entry.get("materials", []),
        }
