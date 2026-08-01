"""Alembic environment configuration.

Loads the database URL from the application's settings so migrations
stay in sync with the running app configuration.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL
from sqlmodel import SQLModel

from alembic import context
from app.core.config import settings
from app.models.session import Session  # noqa: F401
from app.models.thread import Thread  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.notification import NotificationRecord  # noqa: F401
from app.atrisk.state import AtRiskStateRecord  # noqa: F401
from app.models.reminder_event import ReminderEvent  # noqa: F401

# Alembic Config object
config = context.config

# Set up Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Build the database URL from app settings. Built via URL.create() (not an
# f-string) so SQLAlchemy handles percent-encoding of any special characters
# in the username or password -- a raw f-string breaks the moment a password
# contains an unescaped "@", "#", "?", "%", etc. (as hosted-Postgres generated
# passwords, e.g. Supabase's, commonly do).
DATABASE_URL = URL.create(
    "postgresql",
    username=settings.POSTGRES_USER,
    password=settings.POSTGRES_PASSWORD,
    host=settings.POSTGRES_HOST,
    port=settings.POSTGRES_PORT,
    database=settings.POSTGRES_DB,
)

# Point Alembic at our SQLModel metadata for autogenerate support
target_metadata = SQLModel.metadata

# Tables managed by external systems (LangGraph checkpointer, mem0, pgvector)
# that Alembic should never touch.
EXCLUDE_TABLES = {
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
    "checkpoints",
    "longterm_memory",
    "mem0migrations",
}


def include_object(object, name, type_, reflected, compare_to):
    """Filter out tables managed by external systems."""
    if type_ == "table" and name in EXCLUDE_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Emits SQL to stdout instead of executing against the database.
    """
    context.configure(
        url=DATABASE_URL.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an engine and runs migrations against the live database.
    """
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
