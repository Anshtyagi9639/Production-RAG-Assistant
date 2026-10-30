"""The single way to read vectors. Every query is filtered to one workspace."""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from app.rag.indexing import COLLECTION, VectorIndexError, with_retries

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: uuid.UUID
    filename: str
    page: int | None
    chunk_index: int
    score: float
    text: str


def workspace_filter(
    workspace_id: uuid.UUID, document_ids: Sequence[uuid.UUID] | None = None
) -> Filter:
    conditions = [FieldCondition(key="workspace_id", match=MatchValue(value=str(workspace_id)))]
    if document_ids:
        conditions.append(
            FieldCondition(key="document_id", match=MatchAny(any=[str(d) for d in document_ids]))
        )
    return Filter(must=conditions)


async def retrieve(
    client: AsyncQdrantClient,
    query_vector: Sequence[float],
    *,
    workspace_id: uuid.UUID,
    top_k: int,
    score_threshold: float,
    document_ids: Sequence[uuid.UUID] | None = None,
) -> list[RetrievedChunk]:
    """Top-k chunks in the workspace scoring at least `score_threshold` (cosine similarity)."""
    try:
        response = await with_retries(
            lambda: client.query_points(
                COLLECTION,
                query=list(query_vector),
                query_filter=workspace_filter(workspace_id, document_ids),
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
            )
        )
    except Exception as exc:
        logger.warning("vector_search_failed", extra={"error": type(exc).__name__})
        raise VectorIndexError from exc
    chunks = []
    for point in response.points:
        payload = point.payload or {}
        chunks.append(
            RetrievedChunk(
                document_id=uuid.UUID(payload["document_id"]),
                filename=payload["filename"],
                page=payload["page"],
                chunk_index=payload["chunk_index"],
                score=point.score,
                text=payload["text"],
            )
        )
    return chunks


class QueryEmbedder(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...


class KnowledgeRetriever:
    """Embed a query and search one workspace. Search, chat and the agent all use this, so
    there is a single retrieval path and it always carries the workspace filter."""

    def __init__(
        self,
        embedder: QueryEmbedder,
        client: AsyncQdrantClient,
        *,
        top_k: int,
        score_threshold: float,
    ) -> None:
        self._embedder = embedder
        self._client = client
        self._top_k = top_k
        self._score_threshold = score_threshold

    async def search(
        self,
        workspace_id: uuid.UUID,
        query: str,
        *,
        top_k: int | None = None,
        document_ids: Sequence[uuid.UUID] | None = None,
    ) -> list[RetrievedChunk]:
        """Raises EmbeddingError / EmbeddingNotConfiguredError / VectorIndexError."""
        vector = await self._embedder.embed_query(query)
        return await retrieve(
            self._client,
            vector,
            workspace_id=workspace_id,
            top_k=top_k or self._top_k,
            score_threshold=self._score_threshold,
            document_ids=document_ids,
        )
