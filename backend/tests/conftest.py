from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient

from app.core.config import Settings
from app.main import create_app
from app.rag.indexing import ensure_collection
from tests.fakes import TEST_DIMENSIONS

FIXTURES = Path(__file__).parent / "fixtures"
TEST_JWT_SECRET = "test-only-jwt-secret-0123456789abcdef"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        allowed_origins="http://localhost:3000",
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        jwt_secret_key=TEST_JWT_SECRET,
        embedding_dimensions=TEST_DIMENSIONS,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    # The lifespan is not run here, so no connections to Postgres, Redis or Qdrant are opened.
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def qdrant() -> AsyncIterator[AsyncQdrantClient]:
    """qdrant-client's local in-process mode: the real client API and filter semantics,
    without a Qdrant server. Payload indexes are accepted but not used in this mode."""
    client = AsyncQdrantClient(location=":memory:")
    await ensure_collection(client, TEST_DIMENSIONS)
    yield client
    await client.close()
