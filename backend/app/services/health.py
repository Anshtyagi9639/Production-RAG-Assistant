import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.schemas.health import ComponentHealth, HealthReport

HealthCheck = Callable[[], Awaitable[object]]

logger = logging.getLogger(__name__)


def postgres_check(engine: AsyncEngine) -> HealthCheck:
    async def check() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    return check


def redis_check(redis: Redis) -> HealthCheck:
    async def check() -> None:
        await redis.ping()

    return check


def qdrant_check(client: AsyncQdrantClient) -> HealthCheck:
    async def check() -> None:
        await client.get_collections()

    return check


class HealthService:
    """Runs each dependency check concurrently, each bounded by its own timeout."""

    def __init__(self, checks: Mapping[str, HealthCheck], timeout_seconds: float) -> None:
        self._checks = checks
        self._timeout_seconds = timeout_seconds

    async def check(self) -> HealthReport:
        names = list(self._checks)
        results = await asyncio.gather(*(self._run(name, self._checks[name]) for name in names))
        checks = dict(zip(names, results, strict=True))
        healthy = all(result.status == "ok" for result in checks.values())
        return HealthReport(status="ok" if healthy else "degraded", checks=checks)

    async def _run(self, name: str, check: HealthCheck) -> ComponentHealth:
        started = time.perf_counter()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                await check()
        except Exception as exc:
            latency_ms = _elapsed_ms(started)
            logger.warning(
                "health_check_failed", extra={"component": name, "error": type(exc).__name__}
            )
            error = "timeout" if isinstance(exc, TimeoutError) else "unreachable"
            return ComponentHealth(status="unavailable", latency_ms=latency_ms, error=error)
        return ComponentHealth(status="ok", latency_ms=_elapsed_ms(started))


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)
