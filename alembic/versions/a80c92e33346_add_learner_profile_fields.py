"""add learner profile fields.

Revision ID: a80c92e33346
Revises: f0ec8f377133
Create Date: 2026-08-04 11:16:57.606796
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "a80c92e33346"
down_revision: Union[str, Sequence[str], None] = "f0ec8f377133"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("preferred_name", sa.String(length=80), nullable=True),
    )

    op.add_column(
        "user",
        sa.Column("timezone", sa.String(length=64), nullable=True),
    )

    op.add_column(
        "user",
        sa.Column("cohort", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user", "cohort")
    op.drop_column("user", "timezone")
    op.drop_column("user", "preferred_name")