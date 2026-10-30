"""Integration tests against the real MongoDB Atlas cluster.

They use a separate `<MONGODB_DATABASE>_test` database (e.g. `copilot_test`) that is emptied
before each test, so the application's own database is never read or modified.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.db.mongo import Mongo, create_mongo_client
from app.db.mongo_schema import COLLECTIONS, ensure_schema
from app.db.redis import create_redis
from app.main import create_app
from app.storage.local import LocalStorage
from tests.conftest import TEST_JWT_SECRET
from tests.fakes import FakeEmbedder, FakeLLM, RecordingJobQueue


def live_settings() -> Settings:
    """Connection settings from the environment (.env); a fixed JWT secret for tests."""
    return Settings(jwt_secret_key=TEST_JWT_SECRET)


async def _prepare(settings: Settings, database: str) -> None:
    client = create_mongo_client(settings, appname="copilot-tests")
    try:
        await ensure_schema(client[database])
    finally:
        await client.close()


@pytest.fixture(scope="session")
def test_database_name() -> str:
    settings = live_settings()
    name = f"{settings.mongodb_database}_test"
    if name == settings.mongodb_database:
        raise RuntimeError("Refusing to run integration tests against the application database")
    asyncio.run(_prepare(settings, name))
    return name


@pytest.fixture
async def mongo(test_database_name: str) -> AsyncIterator[Mongo]:
    client = create_mongo_client(live_settings(), appname="copilot-tests")
    database = client[test_database_name]
    for spec in COLLECTIONS:
        await database[spec.name].delete_many({})
    yield Mongo(client, database)
    await client.close()


@dataclass
class Api:
    app: FastAPI
    client: AsyncClient
    queue: RecordingJobQueue
    embedder: FakeEmbedder
    llm: FakeLLM
    storage: LocalStorage
    storage_root: Path
    qdrant: AsyncQdrantClient
    mongo: Mongo
    redis: Redis
    settings: Settings


@pytest.fixture
async def api(
    settings: Settings, mongo: Mongo, qdrant: AsyncQdrantClient, tmp_path: Path
) -> AsyncIterator[Api]:
    """The real app on MongoDB Atlas, with the real Redis (REDIS_URL) for rate limits. External
    providers are replaced at their boundary: the job queue records jobs instead of using
    Redis, embeddings come from FakeEmbedder, answers from FakeLLM, and vectors go to
    qdrant-client's in-process mode. tests/live/ covers the real OpenAI and Qdrant Cloud."""
    app = create_app(settings)
    storage_root = tmp_path / "uploads"
    harness = Api(
        app=app,
        client=AsyncClient(transport=ASGITransport(app=app), base_url="http://test"),
        queue=RecordingJobQueue(),
        embedder=FakeEmbedder(),
        llm=FakeLLM(),
        storage=LocalStorage(storage_root),
        storage_root=storage_root,
        qdrant=qdrant,
        mongo=mongo,
        redis=create_redis(live_settings()),
        settings=settings,
    )
    app.state.mongo = mongo
    app.state.storage = harness.storage
    app.state.job_queue = harness.queue
    app.state.qdrant = qdrant
    app.state.query_embedder = harness.embedder
    app.state.llm = harness.llm
    app.state.redis = harness.redis
    async with harness.client:
        yield harness
    await harness.redis.aclose()
