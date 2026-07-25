"""merge migration heads.

Revision ID: af46c8486a9a
Revises: aa4ac4f2b4ce, d4b7f2a91c3e
Create Date: 2026-07-25 10:20:06.005155

"""
from typing import Sequence, Union

import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'af46c8486a9a'
down_revision: Union[str, Sequence[str], None] = ('aa4ac4f2b4ce', 'd4b7f2a91c3e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
