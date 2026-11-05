import pytest

from app.services.health import WORKER_HEARTBEAT_KEY, HealthService, worker_check
from app.workers import settings as worker_settings


class FakeRedis:
    def __init__(self, keys: set[str]) -> None:
        self.keys = keys

    async def exists(self, key: str) -> int:
        return int(key in self.keys)


async def ok() -> None:
    return None


async def test_a_missing_worker_is_reported_without_making_the_api_unhealthy() -> None:
    service = HealthService(
        {"mongodb": ok, "worker": worker_check(FakeRedis(set()))},  # type: ignore[arg-type]
        timeout_seconds=1,
        informational=frozenset({"worker"}),
    )

    report = await service.check()

    assert report.status == "ok"
    assert report.checks["mongodb"].status == "ok"
    assert (report.checks["worker"].status, report.checks["worker"].error) == (
        "unavailable",
        "not_running",
    )


async def test_the_worker_heartbeat_key_means_it_is_running() -> None:
    service = HealthService(
        {"worker": worker_check(FakeRedis({WORKER_HEARTBEAT_KEY}))},  # type: ignore[arg-type]
        timeout_seconds=1,
        informational=frozenset({"worker"}),
    )

    report = await service.check()

    assert report.checks["worker"].status == "ok"


async def test_a_failed_required_check_still_degrades_the_report() -> None:
    async def down() -> None:
        raise ConnectionError

    service = HealthService(
        {"mongodb": down, "worker": ok}, timeout_seconds=1, informational=frozenset({"worker"})
    )

    report = await service.check()

    assert report.status == "degraded"
    assert report.checks["mongodb"].error == "unreachable"


async def test_worker_startup_retries_a_dependency_until_it_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []

    async def no_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(worker_settings.asyncio, "sleep", no_sleep)
    calls = 0

    async def flaky() -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError

    await worker_settings._with_retries("mongodb", flaky)

    assert calls == 3
    assert delays == [2, 4]


async def test_worker_startup_gives_up_after_the_last_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(worker_settings.asyncio, "sleep", no_sleep)

    async def down() -> None:
        raise ConnectionError

    with pytest.raises(ConnectionError):
        await worker_settings._with_retries("mongodb", down)
