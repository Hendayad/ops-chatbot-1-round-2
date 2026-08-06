"""rename user cohort and add session cohort id.

Revision ID: 91532da022bb
Revises: bbd5275b4104
Create Date: 2026-08-06 11:16:36.344156

"""

from typing import Sequence, Union

import sqlmodel  # noqa: F401
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "91532da022bb"
down_revision: Union[str, Sequence[str], None] = "bbd5275b4104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Use the user cohort as the authoritative learner assignment."""

    # Preserve existing values by renaming instead of adding a second column.
    op.alter_column(
        "user",
        "cohort",
        new_column_name="cohort_id",
        existing_type=sa.String(length=80),
        existing_nullable=True,
    )

    # Match the current SQLModel maximum length.
    op.alter_column(
        "user",
        "cohort_id",
        existing_type=sa.String(length=80),
        type_=sa.String(length=100),
        existing_nullable=True,
    )

    op.create_index(
        op.f("ix_user_cohort_id"),
        "user",
        ["cohort_id"],
        unique=False,
    )

    # Store the trusted cohort snapshot on each chat session.
    op.add_column(
        "session",
        sa.Column(
            "cohort_id",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.create_index(
        op.f("ix_session_cohort_id"),
        "session",
        ["cohort_id"],
        unique=False,
    )

    # Backfill existing sessions from their owning users.
    op.execute(
        sa.text(
            """
            UPDATE "session" AS session_record
            SET cohort_id = user_record.cohort_id
            FROM "user" AS user_record
            WHERE session_record.user_id = user_record.id
              AND session_record.cohort_id IS NULL
              AND user_record.cohort_id IS NOT NULL
              AND BTRIM(user_record.cohort_id) <> ''
            """
        )
    )


def downgrade() -> None:
    """Restore the previous user cohort schema."""

    op.drop_index(
        op.f("ix_session_cohort_id"),
        table_name="session",
    )
    op.drop_column("session", "cohort_id")

    op.drop_index(
        op.f("ix_user_cohort_id"),
        table_name="user",
    )

    op.alter_column(
        "user",
        "cohort_id",
        existing_type=sa.String(length=100),
        type_=sa.String(length=80),
        existing_nullable=True,
    )

    op.alter_column(
        "user",
        "cohort_id",
        new_column_name="cohort",
        existing_type=sa.String(length=80),
        existing_nullable=True,
    )
