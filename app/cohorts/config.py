"""Configuration-driven multi-cohort support.

The configuration file maps each cohort to its approved Operations materials.
A new cohort can be added by updating JSON configuration and supplying the
listed files, without changing application code.

Default configuration path:
    cohorts_config.json

Override it with:
    COHORTS_CONFIG_PATH=cohorts_config.json

Expected JSON shape:
{
  "cohort-a": {
    "name": "Cohort A",
    "materials_root": "materials/cohort-a",
    "enabled": true,
    "materials": [
      {
        "title": "Cohort A Schedule",
        "source": "schedule.md",
        "type": "schedule"
      }
    ]
  },
  "cohort-b": {
    "name": "Cohort B",
    "materials_root": "materials/cohort-b",
    "enabled": true,
    "materials": [
      {
        "title": "Cohort B Schedule",
        "source": "schedule.md",
        "type": "schedule"
      }
    ]
  }
}
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.cohorts.scope import normalize_cohort
from app.core.logging import logger
from app.kb.schema import SourceMetadata, SourceType

DEFAULT_CONFIG_PATH = "cohorts_config.json"
_COHORT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")


class ConfigModel(BaseModel):
    """Strict base model for cohort configuration."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class MaterialConfig(ConfigModel):
    """One approved material belonging to a cohort."""

    title: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=1000)
    type: SourceType

    @field_validator("source")
    @classmethod
    def validate_relative_source(cls, value: str) -> str:
        """Reject paths that can escape the configured materials directory."""
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(
                "material source must be a relative path inside materials_root"
            )
        return path.as_posix()


class CohortDefinition(ConfigModel):
    """Validated configuration for one cohort."""

    cohort_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    materials_root: str = Field(min_length=1, max_length=1000)
    enabled: bool = True
    materials: list[MaterialConfig] = Field(default_factory=list)

    @field_validator("cohort_id")
    @classmethod
    def validate_cohort_id(cls, value: str) -> str:
        """Normalize and validate a safe, stable cohort identifier."""
        normalized = normalize_cohort(value)
        if not normalized or not _COHORT_ID_PATTERN.fullmatch(normalized):
            raise ValueError(
                "cohort_id must use lowercase letters, numbers, hyphens, "
                "or underscores"
            )
        return normalized

    @field_validator("materials_root")
    @classmethod
    def normalize_materials_root(cls, value: str) -> str:
        """Normalize the configured directory without requiring it to exist yet."""
        return Path(value).as_posix()

    @field_validator("materials")
    @classmethod
    def reject_duplicate_sources(
        cls,
        materials: list[MaterialConfig],
    ) -> list[MaterialConfig]:
        """Prevent the same source from being configured twice."""
        sources = [material.source for material in materials]
        if len(sources) != len(set(sources)):
            raise ValueError("materials contains duplicate source paths")
        return materials

    def to_source_metadata(self) -> list[SourceMetadata]:
        """Convert configured materials into ingestion-ready metadata."""
        return [
            SourceMetadata(
                title=material.title,
                source=material.source,
                type=material.type,
                cohort=self.cohort_id,
            )
            for material in self.materials
        ]


class CohortConfigLoader:
    """Load and validate cohort definitions from a JSON file.

    The file is read on every call so deployment configuration changes take
    effect without rebuilding the application. Invalid entries are skipped and
    logged. A malformed existing file fails closed: cohort gating remains
    enabled, but no cohort is considered servable.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        """Initialize the loader.

        Args:
            config_path: Optional explicit JSON path. When omitted,
                COHORTS_CONFIG_PATH is used, then ``cohorts_config.json``.
        """
        self.config_path: str | Path = config_path or os.getenv(
            "COHORTS_CONFIG_PATH",
            DEFAULT_CONFIG_PATH,
        )

    @property
    def path(self) -> Path:
        """Return the active configuration path."""
        return Path(self.config_path)

    def config_exists(self) -> bool:
        """Return whether a cohort configuration file was supplied."""
        return self.path.is_file()

    def _read_file(self) -> dict[str, CohortDefinition]:
        """Read all valid cohort definitions."""
        if not self.config_exists():
            return {}

        try:
            raw_data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "cohort_config_unreadable",
                path=str(self.path),
                error=str(exc),
            )
            return {}

        if not isinstance(raw_data, dict):
            logger.warning(
                "cohort_config_not_an_object",
                path=str(self.path),
            )
            return {}

        cohorts: dict[str, CohortDefinition] = {}
        for raw_cohort_id, raw_entry in raw_data.items():
            if not isinstance(raw_cohort_id, str) or not isinstance(
                raw_entry,
                dict,
            ):
                logger.warning(
                    "cohort_config_entry_invalid",
                    cohort_id=str(raw_cohort_id),
                )
                continue

            if "cohort_id" in raw_entry:
                logger.warning(
                    "cohort_config_entry_contains_cohort_id",
                    cohort_id=raw_cohort_id,
                )
                continue

            try:
                definition = CohortDefinition(
                    cohort_id=raw_cohort_id,
                    **raw_entry,
                )
            except ValidationError as exc:
                logger.warning(
                    "cohort_config_entry_invalid",
                    cohort_id=raw_cohort_id,
                    error=str(exc),
                )
                continue

            if definition.cohort_id in cohorts:
                logger.warning(
                    "cohort_config_duplicate_id",
                    cohort_id=definition.cohort_id,
                )
                continue

            cohorts[definition.cohort_id] = definition

        return cohorts

    def list_cohorts(self, *, include_disabled: bool = False) -> list[str]:
        """Return configured cohort IDs in stable order."""
        cohorts = self._read_file()
        return sorted(
            cohort_id
            for cohort_id, definition in cohorts.items()
            if include_disabled or definition.enabled
        )

    def get(self, cohort_id: str | None) -> CohortDefinition | None:
        """Return one enabled cohort definition, or ``None``."""
        normalized = normalize_cohort(cohort_id)
        if not normalized:
            return None

        definition = self._read_file().get(normalized)
        if definition is None or not definition.enabled:
            return None
        return definition

    def is_known_cohort(self, cohort_id: str | None) -> bool:
        """Return whether an enabled cohort exists."""
        return self.get(cohort_id) is not None

    def load_cohort_config(self, cohort_id: str) -> dict[str, Any]:
        """Return one cohort as a plain dictionary.

        This method keeps compatibility with existing callers that expect a
        dictionary rather than a Pydantic model.
        """
        normalized = normalize_cohort(cohort_id)
        definition = self.get(normalized)
        if definition is None:
            return {
                "cohort_id": normalized,
                "name": "",
                "materials_root": "",
                "enabled": False,
                "materials": [],
            }
        return definition.model_dump(mode="json")

    def get_sources(self, cohort_id: str) -> list[SourceMetadata]:
        """Return ingestion-ready sources for one enabled cohort."""
        definition = self.get(cohort_id)
        return definition.to_source_metadata() if definition else []

    def get_materials_root(self, cohort_id: str) -> Path | None:
        """Return the configured materials directory for one cohort."""
        definition = self.get(cohort_id)
        return Path(definition.materials_root) if definition else None


cohort_config = CohortConfigLoader()


def cohort_gating_enabled() -> bool:
    """Return whether multi-cohort configuration is active.

    The existence of the file enables gating even when it is malformed. This
    fails closed instead of silently falling back to another cohort.
    """
    return cohort_config.config_exists()


def is_servable_cohort(cohort_id: str | None) -> bool:
    """Return whether the requested cohort may receive knowledge-base answers."""
    normalized = normalize_cohort(cohort_id)
    if not normalized:
        return False

    if cohort_gating_enabled():
        return cohort_config.is_known_cohort(normalized)

    # Backward-compatible single-cohort mode. It is available only when no
    # cohort configuration file exists.
    default_cohort = normalize_cohort(os.getenv("DEFAULT_COHORT"))
    return bool(default_cohort and normalized == default_cohort)


__all__ = [
    "CohortConfigLoader",
    "CohortDefinition",
    "MaterialConfig",
    "cohort_config",
    "cohort_gating_enabled",
    "is_servable_cohort",
]