"""add first and last name to user.

Revision ID: 8177583fb1a4
Revises: 91532da022bb
Create Date: 2026-08-07 08:52:53.632881

"""

from typing import Sequence, Union

import sqlmodel  # noqa: F401
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8177583fb1a4"
down_revision: Union[str, Sequence[str], None] = "91532da022bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user",
        sa.Column(
            "first_name",
            sqlmodel.sql.sqltypes.AutoString(length=80),
            nullable=True,
        ),
    )

    op.add_column(
        "user",
        sa.Column(
            "last_name",
            sqlmodel.sql.sqltypes.AutoString(length=80),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user", "last_name")
    op.drop_column("user", "first_name")
