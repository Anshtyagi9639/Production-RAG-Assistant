import json

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.ai.embeddings import (
    CachedQueryEmbedder,
    EmbeddingError,
    EmbeddingNotConfiguredError,
    OpenAIEmbedder,
    embed_in_batches,
)
from app.core.config import Settings
from tests.fakes import FakeEmbedder


class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


async def test_texts_are_embedded_in_batches_in_order() -> None:
    embedder = FakeEmbedder()
    texts = [f"text {n}" for n in range(5)]

    vectors = await embed_in_batches(embedder, texts, batch_size=2, max_attempts=1)

    assert [len(call) for call in embedder.document_calls] == [2, 2, 1]
    assert vectors == [embedder.vector(text) for text in texts]


async def test_transient_failures_are_retried_with_exponential_backoff() -> None:
    embedder = FakeEmbedder(fail_times=2)
    sleep = RecordingSleep()

    vectors = await embed_in_batches(
        embedder, ["a", "b"], batch_size=10, max_attempts=3, base_delay_seconds=0.5, sleep=sleep
    )

    assert len(vectors) == 2
    assert sleep.delays == [0.5, 1.0]
    assert len(embedder.document_calls) == 3


async def test_giving_up_after_max_attempts_raises_embedding_error() -> None:
    embedder = FakeEmbedder(fail_times=5)
    sleep = RecordingSleep()

    with pytest.raises(EmbeddingError):
        await embed_in_batches(embedder, ["a"], batch_size=10, max_attempts=3, sleep=sleep)
    assert len(embedder.document_calls) == 3


async def test_missing_credentials_are_not_retried() -> None:
    embedder = FakeEmbedder(error=EmbeddingNotConfiguredError())
    sleep = RecordingSleep()

    with pytest.raises(EmbeddingNotConfiguredError):
        await embed_in_batches(embedder, ["a"], batch_size=10, max_attempts=3, sleep=sleep)
    assert sleep.delays == []


async def test_openai_embedder_without_a_key_refuses_to_call_out(settings: Settings) -> None:
    embedder = OpenAIEmbedder(settings.model_copy(update={"openai_api_key": None}))

    with pytest.raises(EmbeddingNotConfiguredError, match="OPENAI_API_KEY is not set"):
        await embedder.embed_documents(["text"])
    with pytest.raises(EmbeddingNotConfiguredError):
        await embedder.embed_query("text")


class FakeRedis:
    def __init__(self, broken: bool = False) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.broken = broken

    async def get(self, key: str) -> str | None:
        if self.broken:
            raise RedisConnectionError("down")
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        if self.broken:
            raise RedisConnectionError("down")
        self.values[key] = value
        self.ttls[key] = ex


async def test_query_embeddings_are_cached_with_a_ttl() -> None:
    embedder = FakeEmbedder()
    redis = FakeRedis()
    cached = CachedQueryEmbedder(embedder, redis, "text-embedding-3-small", ttl_seconds=600)  # type: ignore[arg-type]

    first = await cached.embed_query("refund window")
    second = await cached.embed_query("refund window")

    assert first == second == embedder.vector("refund window")
    assert embedder.query_calls == ["refund window"]
    [(key, value)] = redis.values.items()
    assert key.startswith("embedding:query:")
    assert "refund" not in key
    assert json.loads(value) == first
    assert redis.ttls[key] == 600


async def test_cache_keys_depend_on_the_model() -> None:
    redis = FakeRedis()
    embedder = FakeEmbedder()
    await CachedQueryEmbedder(embedder, redis, "model-a", 60).embed_query("q")  # type: ignore[arg-type]
    await CachedQueryEmbedder(embedder, redis, "model-b", 60).embed_query("q")  # type: ignore[arg-type]

    assert len(redis.values) == 2
    assert embedder.query_calls == ["q", "q"]


async def test_redis_outage_falls_back_to_the_embedder() -> None:
    embedder = FakeEmbedder()
    cached = CachedQueryEmbedder(embedder, FakeRedis(broken=True), "m", 60)  # type: ignore[arg-type]

    assert await cached.embed_query("q") == embedder.vector("q")
