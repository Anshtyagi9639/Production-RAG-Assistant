"""A dropped connection to the real Redis (REDIS_URL) is survived, not fatal.

Reproduces what took the arq worker down: the network aborts a pooled connection and the
next command fails. The control case shows the failure is real without the retry policy.
"""

from typing import Any

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.db.redis import create_redis
from tests.integration.conftest import live_settings

pytestmark = pytest.mark.integration


async def _abort_pooled_connection(client: Redis) -> None:
    """Kill the TCP connection under the client's only pooled connection, without telling it."""
    assert await client.ping()
    # Deliberately reaches into redis-py's private pool state, so it's treated as untyped.
    pool: Any = client.connection_pool
    [connection] = pool._available_connections
    connection._writer.transport.abort()


async def test_app_client_reconnects_after_the_connection_is_aborted() -> None:
    client = create_redis(live_settings())
    try:
        await _abort_pooled_connection(client)

        assert await client.ping()
        await client.set("copilot:reconnect-test", "ok", ex=10)
        assert await client.get("copilot:reconnect-test") == "ok"
    finally:
        await client.aclose()


async def test_without_the_retry_policy_the_same_drop_fails() -> None:
    client = Redis.from_url(live_settings().redis_url, decode_responses=True)
    try:
        await _abort_pooled_connection(client)

        with pytest.raises(RedisConnectionError):
            await client.ping()
    finally:
        await client.aclose()
