"""merge migration heads.

Revision ID: f2b31211b15c
Revises: 2b6dca4767ee, a7f3c9e21b04
Create Date: 2026-08-02 17:30:58.195969

"""

from typing import Sequence, Union

import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "f2b31211b15c"
down_revision: Union[str, Sequence[str], None] = ("2b6dca4767ee", "a7f3c9e21b04")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
