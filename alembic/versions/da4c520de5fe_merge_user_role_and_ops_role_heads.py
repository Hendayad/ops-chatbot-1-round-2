"""merge user role and ops role heads.

Revision ID: da4c520de5fe
Revises: 5fe45fd45502, e29c14a7d6f8
Create Date: 2026-07-31 10:20:25.564145

"""

from typing import Sequence, Union

import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "da4c520de5fe"
down_revision: Union[str, Sequence[str], None] = ("5fe45fd45502", "e29c14a7d6f8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
