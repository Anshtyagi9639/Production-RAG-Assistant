import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.core.errors import UserFacingError
from app.rag.chunking import Chunk

COLLECTION = "knowledge_chunks"
UPSERT_BATCH_SIZE = 128
MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 0.5

logger = logging.getLogger(__name__)


class VectorIndexError(UserFacingError):
    def __init__(self) -> None:
        super().__init__("The search index is unavailable. Try again later.")


def is_transient(exc: Exception) -> bool:
    """Network failures, 5xx and 429 are worth retrying; other HTTP errors (4xx) are not."""
    if isinstance(exc, UnexpectedResponse):
        return exc.status_code is None or exc.status_code == 429 or exc.status_code >= 500
    return isinstance(
        exc, ResponseHandlingException | httpx.TransportError | TimeoutError | ConnectionError
    )


async def with_retries[T](operation: Callable[[], Awaitable[T]]) -> T:
    """Run a Qdrant call, retrying transient failures with exponential backoff. A cloud load
    balancer can drop an idle pooled connection, so the first call after a quiet period may
    fail once; every operation retried here is idempotent."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await operation()
        except Exception as exc:
            if attempt == MAX_ATTEMPTS or not is_transient(exc):
                raise
            logger.info(
                "vector_index_retry", extra={"attempt": attempt, "error": type(exc).__name__}
            )
            await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1))
    raise AssertionError("unreachable")


async def ensure_collection(client: AsyncQdrantClient, dimensions: int) -> None:
    """Create the collection and its payload indexes if they don't exist yet (idempotent)."""
    if await client.collection_exists(COLLECTION):
        return
    await client.create_collection(
        COLLECTION, vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE)
    )
    for field in ("workspace_id", "document_id"):
        await client.create_payload_index(
            COLLECTION, field_name=field, field_schema=PayloadSchemaType.KEYWORD
        )


def document_filter(document_id: uuid.UUID, workspace_id: uuid.UUID) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="workspace_id", match=MatchValue(value=str(workspace_id))),
            FieldCondition(key="document_id", match=MatchValue(value=str(document_id))),
        ]
    )


class VectorIndex:
    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    async def replace_document(
        self,
        *,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        filename: str,
        created_at: datetime,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        """Remove the document's old points, then upsert one point per chunk."""
        points = [
            PointStruct(
                id=str(chunk.id),
                vector=list(vector),
                payload={
                    "document_id": str(document_id),
                    "workspace_id": str(workspace_id),
                    "filename": filename,
                    "page": chunk.page,
                    "chunk_index": chunk.index,
                    "source": filename if chunk.page is None else f"{filename}, page {chunk.page}",
                    "created_at": created_at.isoformat(),
                    "text": chunk.text,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

        async def write() -> None:
            # Point ids are deterministic, so repeating the whole write after a failure is safe.
            await self._client.delete(
                COLLECTION,
                points_selector=FilterSelector(filter=document_filter(document_id, workspace_id)),
                wait=True,
            )
            for start in range(0, len(points), UPSERT_BATCH_SIZE):
                await self._client.upsert(
                    COLLECTION, points=points[start : start + UPSERT_BATCH_SIZE], wait=True
                )

        try:
            await with_retries(write)
        except Exception as exc:
            logger.warning("vector_index_write_failed", extra={"error": type(exc).__name__})
            raise VectorIndexError from exc

    async def delete_document(self, document_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        try:
            await with_retries(
                lambda: self._client.delete(
                    COLLECTION,
                    points_selector=FilterSelector(
                        filter=document_filter(document_id, workspace_id)
                    ),
                    wait=True,
                )
            )
        except Exception as exc:
            logger.warning("vector_index_delete_failed", extra={"error": type(exc).__name__})
            raise VectorIndexError from exc
