"""merge duplicate heads.

Revision ID: bf3cac30a0c5
Revises: e29c14a7d6f8, fdaea123798d
Create Date: 2026-07-31 07:58:52.768142

"""
from typing import Sequence, Union

import sqlmodel  # noqa: F401
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf3cac30a0c5'
down_revision: Union[str, Sequence[str], None] = ('e29c14a7d6f8', 'fdaea123798d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
