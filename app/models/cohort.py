"""Database-backed cohort configuration and materials registry.

Replaces the JSON-file-backed cohort config (``cohorts_config.json``, read by
``app.cohorts.config.CohortConfigLoader``) with persistent Postgres storage.

The JSON file lives inside the deployed container's filesystem, and Railway
rebuilds that filesystem from the last git commit on every deploy. Any cohort
created or edited at runtime through the admin API was written to that file
on disk, but never committed back to git -- so it silently disappeared the
next time the backend redeployed. Storing cohorts in the database instead
means they survive redeploys like every other piece of application data.

Material *files* (the actual approved document content) still live on disk
under ``materials_root`` -- only cohort metadata and the registry of which
files belong to which cohort move into these tables.
"""

from datetime import date, datetime, UTC

from sqlmodel import Field, Relationship, UniqueConstraint

from app.models.base import BaseModel


class Cohort(BaseModel, table=True):
    """One configured cohort.

    Attributes:
        cohort_id: Stable, URL-safe identifier and primary key.
        name: Human-readable display name.
        materials_root: Relative directory (under ``MATERIALS_BASE_DIR``)
            that approved material files are read from during ingestion.
        enabled: Whether learners can be served answers from this cohort.
        description: Optional free-text description.
        project: Optional project label.
        start_date: Optional program start date.
        end_date: Optional program end date.
        created_at: Inherited from BaseModel.
        updated_at: Last time this row was modified.
        materials: The materials registered for this cohort.
    """

    cohort_id: str = Field(primary_key=True, max_length=100)
    name: str = Field(max_length=200)
    materials_root: str = Field(max_length=1000)
    enabled: bool = Field(default=True)
    description: str | None = Field(default=None, max_length=2000)
    project: str | None = Field(default=None, max_length=200)
    start_date: date | None = Field(default=None)
    end_date: date | None = Field(default=None)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    materials: list["CohortMaterial"] = Relationship(
        back_populates="cohort",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class CohortMaterial(BaseModel, table=True):
    """One approved material registered for a cohort.

    Attributes:
        id: Surrogate primary key.
        cohort_id: Owning cohort.
        title: Human-readable title shown in the admin UI.
        source: Relative file path under the cohort's ``materials_root``.
        type: Material category -- one of ``app.kb.schema.SourceType``'s
            values ("faq", "onboarding", "schedule", "program_doc"), stored
            as plain text rather than a native Postgres enum so this table
            doesn't need to manage its own enum-type migration.
        created_at: Inherited from BaseModel.
        cohort: The owning cohort.
    """

    __table_args__ = (
        UniqueConstraint("cohort_id", "source", name="uq_cohort_material_source"),
    )

    id: int = Field(default=None, primary_key=True)
    cohort_id: str = Field(foreign_key="cohort.cohort_id", index=True)
    title: str = Field(max_length=300)
    source: str = Field(max_length=1000)
    type: str = Field(max_length=50)

    cohort: Cohort = Relationship(back_populates="materials")
