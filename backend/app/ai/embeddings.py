import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.errors import UserFacingError

logger = logging.getLogger(__name__)


class EmbeddingError(UserFacingError):
    """A transient failure talking to the embedding provider. Worth retrying."""

    def __init__(self) -> None:
        super().__init__("The embedding service failed to respond. Try uploading again later.")


class EmbeddingNotConfiguredError(UserFacingError):
    """No provider credentials. Retrying won't help."""

    def __init__(self) -> None:
        super().__init__("Embeddings are not configured on the server (OPENAI_API_KEY is not set).")


class Embedder(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class OpenAIEmbedder:
    """OpenAI embeddings via langchain-openai. Called only from the backend and worker."""

    def __init__(self, settings: Settings) -> None:
        api_key = settings.openai_key
        self._client = (
            OpenAIEmbeddings(
                model=settings.openai_embedding_model,
                dimensions=settings.embedding_dimensions,
                openai_api_key=SecretStr(api_key),
                # Retries are handled by embed_in_batches, with backoff we control and test.
                max_retries=0,
                request_timeout=30,
            )
            if api_key
            else None
        )

    def _require_client(self) -> OpenAIEmbeddings:
        if self._client is None:
            raise EmbeddingNotConfiguredError
        return self._client

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        client = self._require_client()
        try:
            return await client.aembed_documents(texts)
        except Exception as exc:
            logger.warning("embedding_request_failed", extra={"error": type(exc).__name__})
            raise EmbeddingError from exc

    async def embed_query(self, text: str) -> list[float]:
        client = self._require_client()
        try:
            return await client.aembed_query(text)
        except Exception as exc:
            logger.warning("embedding_request_failed", extra={"error": type(exc).__name__})
            raise EmbeddingError from exc


async def embed_in_batches(
    embedder: Embedder,
    texts: list[str],
    *,
    batch_size: int,
    max_attempts: int,
    base_delay_seconds: float = 1.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> list[list[float]]:
    """Embed texts in batches, retrying transient failures with exponential backoff."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        for attempt in range(1, max_attempts + 1):
            try:
                result = await embedder.embed_documents(batch)
                break
            except EmbeddingError:
                if attempt == max_attempts:
                    raise
                await sleep(base_delay_seconds * 2 ** (attempt - 1))
        if len(result) != len(batch):
            raise EmbeddingError
        vectors.extend(result)
    return vectors


class CachedQueryEmbedder:
    """Caches query embeddings in Redis for a short TTL: repeated searches skip the API call.

    Redis being unavailable only disables the cache; it never fails the search.
    """

    def __init__(self, embedder: Embedder, redis: Redis, model: str, ttl_seconds: int) -> None:
        self._embedder = embedder
        self._redis = redis
        self._model = model
        self._ttl_seconds = ttl_seconds

    def _key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self._model}\x00{text}".encode()).hexdigest()
        return f"embedding:query:{digest}"

    async def embed_query(self, text: str) -> list[float]:
        key = self._key(text)
        try:
            cached = await self._redis.get(key)
            if cached is not None:
                vector: list[float] = json.loads(cached)
                return vector
        except RedisError as exc:
            logger.warning("embedding_cache_unavailable", extra={"error": type(exc).__name__})
        vector = await self._embedder.embed_query(text)
        if self._ttl_seconds > 0:
            try:
                await self._redis.set(key, json.dumps(vector), ex=self._ttl_seconds)
            except RedisError as exc:
                logger.warning("embedding_cache_unavailable", extra={"error": type(exc).__name__})
        return vector
