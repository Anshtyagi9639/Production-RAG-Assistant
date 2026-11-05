import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from app.core.errors import is_database_auth_failure
from app.db.mongo import Mongo
from app.schemas.health import ComponentHealth, HealthError, HealthReport

HealthCheck = Callable[[], Awaitable[object]]

logger = logging.getLogger(__name__)


def mongodb_check(mongo: Mongo) -> HealthCheck:
    async def check() -> None:
        await mongo.db.command("ping")

    return check


def redis_check(redis: Redis) -> HealthCheck:
    async def check() -> None:
        await redis.ping()

    return check


# Written by the arq worker every WORKER_HEARTBEAT_SECONDS (arq's default queue and key suffix),
# with an expiry just past that interval: the key exists only while a worker is running.
WORKER_HEARTBEAT_KEY = "arq:queue:health-check"
WORKER_HEARTBEAT_SECONDS = 30


class WorkerNotRunningError(Exception):
    pass


def worker_check(redis: Redis) -> HealthCheck:
    async def check() -> None:
        if not await redis.exists(WORKER_HEARTBEAT_KEY):
            raise WorkerNotRunningError

    return check


def qdrant_check(client: AsyncQdrantClient) -> HealthCheck:
    async def check() -> None:
        await client.get_collections()

    return check


class HealthService:
    """Runs each dependency check concurrently, each bounded by its own timeout.

    `informational` checks are reported but don't make the API unhealthy: the API serves
    requests without them (e.g. the worker, which only processes queued jobs)."""

    def __init__(
        self,
        checks: Mapping[str, HealthCheck],
        timeout_seconds: float,
        informational: frozenset[str] = frozenset(),
    ) -> None:
        self._checks = checks
        self._timeout_seconds = timeout_seconds
        self._informational = informational

    async def check(self) -> HealthReport:
        names = list(self._checks)
        results = await asyncio.gather(*(self._run(name, self._checks[name]) for name in names))
        checks = dict(zip(names, results, strict=True))
        healthy = all(
            result.status == "ok"
            for name, result in checks.items()
            if name not in self._informational
        )
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
            if isinstance(exc, TimeoutError):
                error: HealthError = "timeout"
            elif is_database_auth_failure(exc):
                error = "authentication_failed"
            elif isinstance(exc, WorkerNotRunningError):
                error = "not_running"
            else:
                error = "unreachable"
            return ComponentHealth(status="unavailable", latency_ms=latency_ms, error=error)
        return ComponentHealth(status="ok", latency_ms=_elapsed_ms(started))


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)
