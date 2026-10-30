from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import Settings

# Cloud Redis (e.g. Upstash) can drop long-lived connections. Without retries, a single dropped
# connection fails the command, and in the arq worker it ends the polling loop (the worker
# exits). With these, the client reconnects and retries the command.
REDIS_RETRY_ON: list[type[Exception]] = [RedisConnectionError, RedisTimeoutError]
REDIS_RETRIES = 5
# Ping a pooled connection before reuse if it has been idle this long.
REDIS_HEALTH_CHECK_SECONDS = 30


def redis_retry() -> Retry:
    return Retry(ExponentialBackoff(cap=10, base=0.5), retries=REDIS_RETRIES)


def create_redis(settings: Settings) -> Redis:
    client: Redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        retry=redis_retry(),
        retry_on_error=REDIS_RETRY_ON,
        health_check_interval=REDIS_HEALTH_CHECK_SECONDS,
    )
    return client
