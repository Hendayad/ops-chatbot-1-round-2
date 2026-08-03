"""add user role.

Revision ID: 5fe45fd45502
Revises: fdaea123798d
Create Date: 2026-07-29 19:33:32.519516

"""

from typing import Sequence, Union

import sqlmodel  # noqa: F401
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5fe45fd45502"
down_revision: Union[str, Sequence[str], None] = "fdaea123798d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    user_role_enum = sa.Enum(
        "LEARNER",
        "PROGRAM_LEAD",
        "ADMIN",
        name="userrole"
    )

    user_role_enum.create(
        op.get_bind(),
        checkfirst=True
    )

    op.add_column(
        "user",
        sa.Column(
            "role",
            user_role_enum,
            nullable=False,
            server_default="LEARNER"
        )
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(
        "user",
        "role"
    )

    user_role_enum = sa.Enum(
        "LEARNER",
        "ADMIN",
        name="userrole"
    )

    user_role_enum.drop(
        op.get_bind(),
        checkfirst=True
    )
    # ### end Alembic commands ###
