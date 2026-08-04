"""add learner_profile table.

Revision ID: e6a5b8c9d0e1
Revises: fdaea123798d
Create Date: 2026-08-02 23:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "e6a5b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "fdaea123798d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "learner_profiles",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), primary_key=True, nullable=False),
        sa.Column("preferred_name", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=True),
        sa.Column("timezone", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("cohort", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=True),
    )
    op.create_index(
        op.f("ix_learner_profiles_user_id"),
        "learner_profiles",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_learner_profiles_user_id"), table_name="learner_profiles")
    op.drop_table("learner_profiles")
