"""
KMRL NexusAI — Alembic Environment
====================================
Supports both sync (for migration scripts) and async (for runtime) modes.
"""
import asyncio
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Alembic Config object — gives access to values in alembic.ini
config = context.config

# Interpret logging config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so autogenerate can detect changes
from app.models.models import Base  # noqa: E402

target_metadata = Base.metadata

# Override sqlalchemy.url from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://kmrl:kmrl_secret@localhost:5432/kmrl_nexusai"
)

# For Alembic (sync), convert asyncpg → psycopg2
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "+psycopg2").replace(
    "postgresql+psycopg2", "postgresql"
)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Configures context with just a URL and no Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    context.configure(
        url=SYNC_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using an async engine.
    An Engine is created and associated with a Connection.
    """
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
