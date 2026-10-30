import uuid
from types import TracebackType
from typing import Any

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.errors import AppError
from app.core.rate_limit import RateLimiter


class FakePipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._ops: list[tuple[str, str]] = []

    async def __aenter__(self) -> "FakePipeline":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def incr(self, key: str) -> None:
        self._ops.append(("incr", key))

    def expire(self, key: str, seconds: int) -> None:
        self._ops.append(("expire", key))
        self._redis.ttls[key] = seconds

    async def execute(self) -> list[Any]:
        if self._redis.down:
            raise RedisConnectionError("down")
        results: list[Any] = []
        for op, key in self._ops:
            if op == "incr":
                self._redis.counts[key] = self._redis.counts.get(key, 0) + 1
                results.append(self._redis.counts[key])
            else:
                results.append(True)
        return results


class FakeRedis:
    def __init__(self, down: bool = False) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.down = down

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        return FakePipeline(self)


async def test_requests_over_the_limit_get_429_with_retry_after() -> None:
    redis = FakeRedis()
    limiter = RateLimiter(redis, limit=2, window_seconds=60)  # type: ignore[arg-type]
    user = uuid.uuid4()

    await limiter.check("chat", user)
    await limiter.check("chat", user)
    with pytest.raises(AppError) as exc_info:
        await limiter.check("chat", user)

    error = exc_info.value
    assert (error.status_code, error.code) == (429, "rate_limited")
    assert error.headers is not None
    assert 1 <= int(error.headers["Retry-After"]) <= 60
    assert all(ttl == 60 for ttl in redis.ttls.values())


async def test_limits_are_per_user_and_per_scope() -> None:
    limiter = RateLimiter(FakeRedis(), limit=1, window_seconds=60)  # type: ignore[arg-type]
    alice, bob = uuid.uuid4(), uuid.uuid4()

    await limiter.check("chat", alice)
    await limiter.check("chat", bob)
    await limiter.check("search", alice)


async def test_redis_outage_allows_the_request() -> None:
    limiter = RateLimiter(FakeRedis(down=True), limit=1, window_seconds=60)  # type: ignore[arg-type]

    for _ in range(3):
        await limiter.check("chat", uuid.uuid4())
