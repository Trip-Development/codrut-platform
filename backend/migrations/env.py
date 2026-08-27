from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from codrut.core.config import get_settings
from codrut.core.database import Base
from codrut.modules.assignments import models as assignment_models  # noqa: F401
from codrut.modules.communications import models as communication_models  # noqa: F401
from codrut.modules.companies import models as company_models  # noqa: F401
from codrut.modules.forms import models as form_models  # noqa: F401
from codrut.modules.identity import models as identity_models  # noqa: F401
from codrut.modules.practice import models as practice_models  # noqa: F401
from codrut.modules.scoring import models as scoring_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _timeout_ms(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer number of milliseconds.") from exc
    if not 1 <= value <= 3_600_000:
        raise RuntimeError(f"{name} must be between 1 and 3600000 milliseconds.")
    return value


def get_url() -> str:
    return str(get_settings().database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("select set_config('lock_timeout', :value, true)"),
                {"value": f"{_timeout_ms('CODRUT_MIGRATION_LOCK_TIMEOUT_MS', 5000)}ms"},
            )
            connection.execute(
                text("select set_config('statement_timeout', :value, true)"),
                {"value": (f"{_timeout_ms('CODRUT_MIGRATION_STATEMENT_TIMEOUT_MS', 900000)}ms")},
            )
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
