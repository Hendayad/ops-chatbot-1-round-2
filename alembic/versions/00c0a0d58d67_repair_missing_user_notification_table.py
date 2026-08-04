"""repair missing user notification table.

Revision ID: 00c0a0d58d67
Revises: a80c92e33346
Create Date: 2026-08-04 12:46:27.437097
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00c0a0d58d67"
down_revision: Union[str, Sequence[str], None] = "a80c92e33346"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create missing user_notification table."""

    op.create_table(
        "user_notification",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),

        sa.Column(
            "user_id",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "title",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "category",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_user_notification_user_id",
        "user_notification",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove user_notification table."""

    op.drop_index(
        "ix_user_notification_user_id",
        table_name="user_notification",
    )

    op.drop_table("user_notification")