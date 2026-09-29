from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.health import HealthService, postgres_check, qdrant_check, redis_check


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request. Services own transaction boundaries (`session.begin()`)."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_health_service(request: Request) -> HealthService:
    state = request.app.state
    return HealthService(
        {
            "postgres": postgres_check(state.engine),
            "redis": redis_check(state.redis),
            "qdrant": qdrant_check(state.qdrant),
        },
        timeout_seconds=state.settings.health_check_timeout_seconds,
    )
