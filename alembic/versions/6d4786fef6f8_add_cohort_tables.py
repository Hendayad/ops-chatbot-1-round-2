"""add cohort and cohortmaterial tables, seeded from cohorts_config.json.

Revision ID: 6d4786fef6f8
Revises: 8177583fb1a4
Create Date: 2026-08-11 18:00:00.000000

Cohorts used to live only in cohorts_config.json, a file tracked in git and
read/written directly on the running container's disk. Railway rebuilds that
disk from the last git commit on every deploy, so any cohort created or
edited at runtime (through the admin API) was silently lost on the next
deploy. This migration creates real tables for cohorts and their registered
materials, and seeds them with the cohorts currently committed in
cohorts_config.json (cohort-a, cohort-b, cohort-d, cohort-demo) so the
existing, working cohorts carry over exactly as they are today.
"""

from typing import Sequence, Union

import sqlmodel  # noqa: F401
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6d4786fef6f8"
down_revision: Union[str, Sequence[str], None] = "8177583fb1a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### tables ###
    op.create_table(
        "cohort",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("cohort_id", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("materials_root", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=True),
        sa.Column("project", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cohort_id"),
    )

    op.create_table(
        "cohortmaterial",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cohort_id", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.ForeignKeyConstraint(["cohort_id"], ["cohort.cohort_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cohort_id", "source", name="uq_cohort_material_source"),
    )
    op.create_index(op.f("ix_cohortmaterial_cohort_id"), "cohortmaterial", ["cohort_id"], unique=False)
    # ### end tables ###

    # ### seed data, matching cohorts_config.json as committed today ###
    cohort_table = sa.table(
        "cohort",
        sa.column("cohort_id", sa.String),
        sa.column("name", sa.String),
        sa.column("materials_root", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("description", sa.String),
        sa.column("project", sa.String),
        sa.column("start_date", sa.Date),
        sa.column("end_date", sa.Date),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    material_table = sa.table(
        "cohortmaterial",
        sa.column("cohort_id", sa.String),
        sa.column("title", sa.String),
        sa.column("source", sa.String),
        sa.column("type", sa.String),
        sa.column("created_at", sa.DateTime),
    )

    now = sa.func.now()

    op.bulk_insert(
        cohort_table,
        [
            {
                "cohort_id": "cohort-a",
                "name": "Cohort A",
                "materials_root": "materials/cohort-a",
                "enabled": True,
                "description": None,
                "project": None,
                "start_date": None,
                "end_date": None,
            },
            {
                "cohort_id": "cohort-b",
                "name": "Cohort B",
                "materials_root": "materials/cohort-b",
                "enabled": True,
                "description": None,
                "project": None,
                "start_date": None,
                "end_date": None,
            },
            {
                "cohort_id": "cohort-d",
                "name": "Cohort D",
                "materials_root": "materials/cohort-d",
                "enabled": True,
                "description": "This is a new cohort with letter 'D'",
                "project": "AI system",
                "start_date": "2026-08-07",
                "end_date": "2026-08-31",
            },
            {
                "cohort_id": "cohort-demo",
                "name": "Cohort Demo",
                "materials_root": "materials/cohort-a",
                "enabled": True,
                "description": "Demo cohort for hamza/hend test accounts, mapped to Cohort A's approved materials.",
                "project": None,
                "start_date": None,
                "end_date": None,
            },
        ],
    )

    op.bulk_insert(
        material_table,
        [
            {"cohort_id": "cohort-a", "title": "Cohort A FAQ", "source": "faqs/faq.md", "type": "faq"},
            {"cohort_id": "cohort-a", "title": "Cohort A Schedule", "source": "schedules/schedule.md", "type": "schedule"},
            {"cohort_id": "cohort-a", "title": "Cohort A Getting Started", "source": "onboarding/getting-started.md", "type": "onboarding"},
            {"cohort_id": "cohort-a", "title": "Cohort A Learner Handbook", "source": "docs/handbook.md", "type": "program_doc"},
            {"cohort_id": "cohort-b", "title": "Cohort B FAQ", "source": "faqs/faq.md", "type": "faq"},
            {"cohort_id": "cohort-b", "title": "Cohort B Schedule", "source": "schedules/schedule.md", "type": "schedule"},
            {"cohort_id": "cohort-b", "title": "Cohort B Getting Started", "source": "onboarding/getting-started.md", "type": "onboarding"},
            {"cohort_id": "cohort-b", "title": "Cohort B Learner Handbook", "source": "docs/handbook.md", "type": "program_doc"},
            {"cohort_id": "cohort-d", "title": "AI Track rules", "source": "ai_track_rules.txt", "type": "program_doc"},
            {"cohort_id": "cohort-d", "title": "Agent Project", "source": "ai_operations_support_agent_project_description.txt", "type": "program_doc"},
            {"cohort_id": "cohort-demo", "title": "Cohort Demo FAQ", "source": "faqs/faq.md", "type": "faq"},
            {"cohort_id": "cohort-demo", "title": "Cohort Demo Schedule", "source": "schedules/schedule.md", "type": "schedule"},
            {"cohort_id": "cohort-demo", "title": "Cohort Demo Getting Started", "source": "onboarding/getting-started.md", "type": "onboarding"},
            {"cohort_id": "cohort-demo", "title": "Cohort Demo Learner Handbook", "source": "docs/handbook.md", "type": "program_doc"},
        ],
    )

    # created_at/updated_at have server-side-friendly defaults from SQLModel
    # at the application layer, but bulk_insert bypasses those -- backfill
    # them explicitly so the seeded rows aren't left with NULL timestamps.
    op.execute(cohort_table.update().values(created_at=now, updated_at=now))
    op.execute(material_table.update().values(created_at=now))
    # ### end seed data ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_cohortmaterial_cohort_id"), table_name="cohortmaterial")
    op.drop_table("cohortmaterial")
    op.drop_table("cohort")
