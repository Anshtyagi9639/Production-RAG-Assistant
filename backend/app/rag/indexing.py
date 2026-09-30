import logging
import uuid
from collections.abc import Sequence
from datetime import datetime

from qdrant_client import AsyncQdrantClient
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

logger = logging.getLogger(__name__)


class VectorIndexError(UserFacingError):
    def __init__(self) -> None:
        super().__init__("The search index is unavailable. Try again later.")


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
        try:
            await self._client.delete(
                COLLECTION,
                points_selector=FilterSelector(filter=document_filter(document_id, workspace_id)),
                wait=True,
            )
            for start in range(0, len(points), UPSERT_BATCH_SIZE):
                await self._client.upsert(
                    COLLECTION, points=points[start : start + UPSERT_BATCH_SIZE], wait=True
                )
        except Exception as exc:
            logger.warning("vector_index_write_failed", extra={"error": type(exc).__name__})
            raise VectorIndexError from exc

    async def delete_document(self, document_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        try:
            await self._client.delete(
                COLLECTION,
                points_selector=FilterSelector(filter=document_filter(document_id, workspace_id)),
                wait=True,
            )
        except Exception as exc:
            logger.warning("vector_index_delete_failed", extra={"error": type(exc).__name__})
            raise VectorIndexError from exc
