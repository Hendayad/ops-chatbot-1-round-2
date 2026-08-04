"""add learner profile fields

Revision ID: f0ec8f377133
Revises: f2b31211b15c
Create Date: 2026-xx-xx
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f0ec8f377133"
down_revision: Union[str, Sequence[str], None] = "f2b31211b15c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "preferred_name",
            sa.String(length=80),
            nullable=True,
        ),
    )

    op.add_column(
        "user",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "user",
        sa.Column(
            "cohort",
            sa.String(length=80),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("user", "cohort")
    op.drop_column("user", "timezone")
    op.drop_column("user", "preferred_name")