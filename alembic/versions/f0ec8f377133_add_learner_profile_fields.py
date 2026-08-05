"""add learner profile fields.

Revision ID: f0ec8f377133
Revises: f2b31211b15c
"""

from typing import Sequence, Union

revision: str = "f0ec8f377133"
down_revision: Union[str, Sequence[str], None] = "f2b31211b15c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Columns already exist.
    # This migration only marks the revision as applied.
    pass


def downgrade() -> None:
    pass