"""add notification preferences.

Revision ID: cf0499e7ef1e
Revises: aa4ac4f2b4ce
Create Date: 2026-07-23 23:34:03.000694

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "cf0499e7ef1e"
down_revision: Union[str, Sequence[str], None] = "aa4ac4f2b4ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notification_preferences",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("opted_out", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("session_reminders", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deadline_reminders", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("nudges", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_notification_preferences_user_id",
        table_name="notification_preferences",
    )

    op.drop_table("notification_preferences")