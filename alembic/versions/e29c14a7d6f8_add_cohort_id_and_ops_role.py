"""add cohort_id to atriskstaterecord and is_ops to user.

Revision ID: e29c14a7d6f8
Revises: af46c8486a9a
Create Date: 2026-07-28 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel  # noqa: F401

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e29c14a7d6f8"
down_revision: Union[str, Sequence[str], None] = "af46c8486a9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("atriskstaterecord", sa.Column("cohort_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index(
        op.f("ix_atriskstaterecord_cohort_id"), "atriskstaterecord", ["cohort_id"], unique=False
    )

    op.add_column(
        "user",
        sa.Column("is_ops", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Drop the server_default once existing rows are backfilled -- keeps
    # the *application-level* default (User.is_ops = False in the SQLModel
    # field) as the single source of truth going forward, matching how
    # every other boolean/default on this model behaves. The server_default
    # above only exists so this ADD COLUMN doesn't fail against existing
    # non-null rows.
    op.alter_column("user", "is_ops", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user", "is_ops")
    op.drop_index(op.f("ix_atriskstaterecord_cohort_id"), table_name="atriskstaterecord")
    op.drop_column("atriskstaterecord", "cohort_id")
