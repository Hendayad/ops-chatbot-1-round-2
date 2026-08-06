"""merge current migration heads.

Revision ID: bbd5275b4104
Revises: 00c0a0d58d67, e6a5b8c9d0e1
Create Date: 2026-08-06 11:15:24.064221

"""

from typing import Sequence, Union

import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "bbd5275b4104"
down_revision: Union[str, Sequence[str], None] = ("00c0a0d58d67", "e6a5b8c9d0e1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
