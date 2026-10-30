import logging
import time
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.errors import AppError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window request counter per user and scope, kept in Redis.

    If Redis is unavailable the request is allowed: rate limiting protects provider costs but
    must not take the product down with it.
    """

    def __init__(self, redis: Redis, *, limit: int, window_seconds: int) -> None:
        self._redis = redis
        self._limit = limit
        self._window = window_seconds

    async def check(self, scope: str, user_id: uuid.UUID) -> None:
        now = int(time.time())
        window_start = now - now % self._window
        key = f"ratelimit:{scope}:{user_id}:{window_start}"
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, self._window)
                count, _ = await pipe.execute()
        except RedisError as exc:
            logger.warning("rate_limit_unavailable", extra={"error": type(exc).__name__})
            return
        if int(count) > self._limit:
            retry_after = max(1, window_start + self._window - now)
            raise AppError(
                429,
                "rate_limited",
                "Too many requests. Wait a moment and try again.",
                headers={"Retry-After": str(retry_after)},
            )
