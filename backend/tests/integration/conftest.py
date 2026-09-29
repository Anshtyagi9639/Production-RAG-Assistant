import asyncio
import re
from collections.abc import AsyncIterator

import pytest
from alembic import command
from sqlalchemy import URL, make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from tests.helpers import alembic_config


async def _create_database_if_missing(url: URL) -> None:
    database = url.database or ""
    if not re.fullmatch(r"\w+", database):
        raise ValueError(f"Unsafe test database name: {database!r}")
    admin = create_async_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    async with admin.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{database}"'))
    await admin.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """A separate `<name>_test` database on the configured server, rebuilt with Alembic.

    Never the application database itself, so running tests cannot wipe development data.
    """
    app_url = make_url(Settings().database_url)
    url = app_url.set(database=f"{app_url.database}_test")
    asyncio.run(_create_database_if_missing(url))
    rendered = url.render_as_string(hide_password=False)
    config = alembic_config(rendered)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return rendered


@pytest.fixture
async def db_session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    """A session inside an outer transaction that is rolled back after each test."""
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()
