import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from sqlalchemy import URL, make_url, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.main import create_app
from app.storage.local import LocalStorage
from tests.conftest import TEST_JWT_SECRET
from tests.fakes import FakeEmbedder, RecordingJobQueue
from tests.helpers import alembic_config


def live_settings() -> Settings:
    """Connection URLs from the environment (.env); a fixed JWT secret for tests."""
    return Settings(jwt_secret_key=TEST_JWT_SECRET)


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
    app_url = make_url(live_settings().database_url)
    url = app_url.set(database=f"{app_url.database}_test")
    asyncio.run(_create_database_if_missing(url))
    rendered = url.render_as_string(hide_password=False)
    config = alembic_config(rendered)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return rendered


@pytest.fixture
async def db_connection(test_database_url: str) -> AsyncIterator[AsyncConnection]:
    """One connection per test inside a transaction that is rolled back afterwards."""
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def session_factory(db_connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    """Sessions whose commits become SAVEPOINTs inside the test's outer transaction."""
    return async_sessionmaker(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@dataclass
class Api:
    client: AsyncClient
    queue: RecordingJobQueue
    embedder: FakeEmbedder
    storage: LocalStorage
    storage_root: Path
    qdrant: AsyncQdrantClient
    session_factory: async_sessionmaker[AsyncSession]
    settings: Settings


@pytest.fixture
async def api(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    qdrant: AsyncQdrantClient,
    tmp_path: Path,
) -> AsyncIterator[Api]:
    """The real app and PostgreSQL. External providers are replaced at their boundary: the
    job queue records jobs instead of using Redis, and embeddings come from FakeEmbedder."""
    app = create_app(settings)
    storage_root = tmp_path / "uploads"
    harness = Api(
        client=AsyncClient(transport=ASGITransport(app=app), base_url="http://test"),
        queue=RecordingJobQueue(),
        embedder=FakeEmbedder(),
        storage=LocalStorage(storage_root),
        storage_root=storage_root,
        qdrant=qdrant,
        session_factory=session_factory,
        settings=settings,
    )
    app.state.session_factory = session_factory
    app.state.storage = harness.storage
    app.state.job_queue = harness.queue
    app.state.qdrant = qdrant
    app.state.query_embedder = harness.embedder
    async with harness.client:
        yield harness
