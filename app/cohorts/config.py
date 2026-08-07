"""Configuration-driven multi-cohort support.

The configuration file maps each cohort to its approved Operations materials.
A new cohort can be added either by editing the JSON configuration directly,
or through the mutation methods on ``CohortConfigLoader`` (used by the
``/kb/cohorts`` API routes), without changing application code.

Default configuration path:
    cohorts_config.json

Override it with:
    COHORTS_CONFIG_PATH=cohorts_config.json

Materials for newly created cohorts are written under:
    MATERIALS_BASE_DIR (default: current working directory)
joined with each cohort's ``materials_root``.

Expected JSON shape:
{
  "cohort-a": {
    "name": "Cohort A",
    "materials_root": "materials/cohort-a",
    "enabled": true,
    "description": "Optional free-text description",
    "project": "Optional project label",
    "start_date": "2026-01-05",
    "end_date": "2026-04-30",
    "materials": [
      {
        "title": "Cohort A Schedule",
        "source": "schedule.md",
        "type": "schedule"
      }
    ]
  }
}
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import threading
from datetime import date
from pathlib import Path
from typing import Any
import shutil

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.cohorts.scope import normalize_cohort
from app.core.logging import logger
from app.kb.schema import SourceMetadata, SourceType

DEFAULT_CONFIG_PATH = "cohorts_config.json"
_COHORT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")
_SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


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
    description: str | None = Field(default=None, max_length=2000)
    project: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
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
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("materials_root must be a relative, non-escaping path")
        return path.as_posix()

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

    @model_validator(mode="after")
    def validate_date_range(self) -> "CohortDefinition":
        """Ensure the cohort's end date does not precede its start date."""
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self

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


def _slugify_cohort_id(name: str) -> str:
    """Derive a URL/JSON-safe cohort id from a human-readable name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "cohort"


class CohortConfigError(ValueError):
    """Raised when a cohort mutation fails validation."""


class CohortNotFoundError(CohortConfigError):
    """Raised when an operation targets a cohort that does not exist."""


class CohortAlreadyExistsError(CohortConfigError):
    """Raised when creating a cohort whose id already exists."""


class MaterialNotFoundError(CohortConfigError):
    """Raised when removing a material that isn't configured."""


class CohortConfigLoader:
    """Load, validate, and mutate cohort definitions in a JSON file.

    The file is read on every call so deployment configuration changes take
    effect without rebuilding the application. Invalid entries are skipped
    and logged on read. A malformed existing file fails closed: cohort
    gating remains enabled, but no cohort is considered servable.

    Mutations (create/update/delete cohort, add/remove material) are
    serialized with an in-process lock and written atomically so concurrent
    API requests can't corrupt the file. This guards against races within a
    single process; if you run multiple worker processes, put a file lock
    (e.g. via ``filelock``) around ``_write_file`` as well.
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
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        """Return the active configuration path."""
        return Path(self.config_path)

    @property
    def materials_base_dir(self) -> Path:
        """Return the base directory that ``materials_root`` values are relative to."""
        return Path(os.getenv("MATERIALS_BASE_DIR", "."))

    def config_exists(self) -> bool:
        """Return whether a cohort configuration file was supplied."""
        return self.path.is_file()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

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

    def list_definitions(
        self, *, include_disabled: bool = False
    ) -> list[CohortDefinition]:
        """Return full cohort definitions in stable (name) order."""
        cohorts = self._read_file()
        return sorted(
            (
                definition
                for definition in cohorts.values()
                if include_disabled or definition.enabled
            ),
            key=lambda definition: definition.name.lower(),
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

    def get_any(self, cohort_id: str | None) -> CohortDefinition | None:
        """Return a cohort definition regardless of its enabled state."""
        normalized = normalize_cohort(cohort_id)
        if not normalized:
            return None
        return self._read_file().get(normalized)

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
                "description": None,
                "project": None,
                "start_date": None,
                "end_date": None,
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

    def get_materials_abs_path(self, cohort_id: str) -> Path | None:
        """Return the resolved, absolute materials directory for a cohort."""
        definition = self.get_any(cohort_id)
        if definition is None:
            return None
        return self.materials_base_dir / definition.materials_root

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def _write_file(self, cohorts: dict[str, CohortDefinition]) -> None:
        """Atomically persist all cohort definitions back to the config file."""
        payload = {
            cohort_id: definition.model_dump(mode="json", exclude={"cohort_id"})
            for cohort_id, definition in cohorts.items()
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent) or ".",
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(payload, tmp_file, indent=2, sort_keys=True)
                tmp_file.write("\n")
            os.replace(tmp_name, self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    def create_cohort(
        self,
        *,
        name: str,
        materials_root: str | None = None,
        description: str | None = None,
        project: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        enabled: bool = True,
    ) -> CohortDefinition:
        """Create and persist a new cohort, returning its validated definition.

        Raises:
            CohortAlreadyExistsError: if the derived/normalized id collides.
            CohortConfigError: if the resulting definition fails validation.
        """
        with self._lock:
            cohorts = self._read_file()

            base_id = _slugify_cohort_id(name)
            candidate_id = base_id
            suffix = 2
            while candidate_id in cohorts:
                candidate_id = f"{base_id}-{suffix}"
                suffix += 1

            resolved_root = materials_root or f"materials/{candidate_id}"

            try:
                definition = CohortDefinition(
                    cohort_id=candidate_id,
                    name=name,
                    materials_root=resolved_root,
                    enabled=enabled,
                    description=description,
                    project=project,
                    start_date=start_date,
                    end_date=end_date,
                    materials=[],
                )
            except ValidationError as exc:
                raise CohortConfigError(str(exc)) from exc

            cohorts[definition.cohort_id] = definition
            self._write_file(cohorts)

            (self.materials_base_dir / definition.materials_root).mkdir(
                parents=True, exist_ok=True
            )

            logger.info("cohort_created", cohort_id=definition.cohort_id)
            return definition

    def update_cohort(
        self,
        cohort_id: str,
        *,
        name: str | None = None,
        enabled: bool | None = None,
        description: str | None = ...,  # type: ignore[assignment]
        project: str | None = ...,  # type: ignore[assignment]
        start_date: date | None = ...,  # type: ignore[assignment]
        end_date: date | None = ...,  # type: ignore[assignment]
    ) -> CohortDefinition:
        """Update mutable fields on an existing cohort.

        Fields left as the default sentinel (``...``) are left unchanged;
        pass ``None`` explicitly to clear an optional field.

        Raises:
            CohortNotFoundError: if no cohort with this id exists.
            CohortConfigError: if the resulting definition fails validation.
        """
        normalized = normalize_cohort(cohort_id)
        with self._lock:
            cohorts = self._read_file()
            existing = cohorts.get(normalized) if normalized else None
            if existing is None:
                raise CohortNotFoundError(f"cohort '{cohort_id}' does not exist")

            updated_fields = existing.model_dump(mode="python")
            if name is not None:
                updated_fields["name"] = name
            if enabled is not None:
                updated_fields["enabled"] = enabled
            if description is not ...:
                updated_fields["description"] = description
            if project is not ...:
                updated_fields["project"] = project
            if start_date is not ...:
                updated_fields["start_date"] = start_date
            if end_date is not ...:
                updated_fields["end_date"] = end_date

            try:
                updated = CohortDefinition(**updated_fields)
            except ValidationError as exc:
                raise CohortConfigError(str(exc)) from exc

            cohorts[updated.cohort_id] = updated
            self._write_file(cohorts)
            logger.info("cohort_updated", cohort_id=updated.cohort_id)
            return updated

    def delete_cohort(self, cohort_id: str) -> None:
        """Delete a cohort and all of its uploaded materials."""

        normalized = normalize_cohort(cohort_id)

        with self._lock:
            cohorts = self._read_file()

            if not normalized or normalized not in cohorts:
                raise CohortNotFoundError(
                    f"cohort '{cohort_id}' does not exist"
                )

            definition = cohorts[normalized]

            materials_dir = (
                self.materials_base_dir /
                definition.materials_root
            )

            if materials_dir.exists():
                shutil.rmtree(materials_dir)

            del cohorts[normalized]

            self._write_file(cohorts)

            logger.info(
                "cohort_deleted",
                cohort_id=normalized,
            )

    def add_material(
        self,
        cohort_id: str,
        *,
        title: str,
        source: str,
        type: SourceType,
    ) -> CohortDefinition:
        """Add one material entry to a cohort.

        Raises:
            CohortNotFoundError: if no cohort with this id exists.
            CohortConfigError: if the material or resulting definition is invalid
                (including a duplicate ``source``).
        """
        normalized = normalize_cohort(cohort_id)
        with self._lock:
            cohorts = self._read_file()
            existing = cohorts.get(normalized) if normalized else None
            if existing is None:
                raise CohortNotFoundError(f"cohort '{cohort_id}' does not exist")

            try:
                new_material = MaterialConfig(title=title, source=source, type=type)
            except ValidationError as exc:
                raise CohortConfigError(str(exc)) from exc

            if any(m.source == new_material.source for m in existing.materials):
                raise CohortConfigError(
                    f"material source '{new_material.source}' already exists "
                    f"for cohort '{normalized}'"
                )

            try:
                updated = existing.model_copy(
                    update={"materials": [*existing.materials, new_material]}
                )
                updated = CohortDefinition(**updated.model_dump(mode="python"))
            except ValidationError as exc:
                raise CohortConfigError(str(exc)) from exc

            cohorts[updated.cohort_id] = updated
            self._write_file(cohorts)
            logger.info(
                "cohort_material_added",
                cohort_id=updated.cohort_id,
                source=new_material.source,
            )
            return updated

    def remove_material(self, cohort_id: str, source: str) -> CohortDefinition:
        """Remove one material entry from a cohort by its ``source`` path.

        Raises:
            CohortNotFoundError: if no cohort with this id exists.
            MaterialNotFoundError: if no material has that ``source``.
        """
        normalized = normalize_cohort(cohort_id)
        normalized_source = Path(source).as_posix()
        with self._lock:
            cohorts = self._read_file()
            existing = cohorts.get(normalized) if normalized else None
            if existing is None:
                raise CohortNotFoundError(f"cohort '{cohort_id}' does not exist")

            remaining = [
                m for m in existing.materials if m.source != normalized_source
            ]
            if len(remaining) == len(existing.materials):
                raise MaterialNotFoundError(
                    f"material '{source}' not found for cohort '{normalized}'"
                )

            updated = existing.model_copy(update={"materials": remaining})
            cohorts[updated.cohort_id] = updated
            self._write_file(cohorts)
            logger.info(
                "cohort_material_removed",
                cohort_id=updated.cohort_id,
                source=normalized_source,
            )
            return updated


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
    "CohortAlreadyExistsError",
    "CohortConfigError",
    "CohortConfigLoader",
    "CohortDefinition",
    "CohortNotFoundError",
    "MaterialConfig",
    "MaterialNotFoundError",
    "cohort_config",
    "cohort_gating_enabled",
    "is_servable_cohort",
]