import uuid
from typing import Protocol

from qdrant_client import AsyncQdrantClient

from app.ai.embeddings import EmbeddingError, EmbeddingNotConfiguredError
from app.ai.retrieval import retrieve
from app.core.config import Settings
from app.core.errors import AppError
from app.rag.indexing import VectorIndexError
from app.schemas.documents import SearchRequest, SearchResponse, SearchResult

SNIPPET_LENGTH = 300


class QueryEmbedder(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...


def make_snippet(text: str, length: int = SNIPPET_LENGTH) -> str:
    text = " ".join(text.split())
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + "…"


class SearchService:
    def __init__(
        self, embedder: QueryEmbedder, qdrant: AsyncQdrantClient, settings: Settings
    ) -> None:
        self._embedder = embedder
        self._qdrant = qdrant
        self._settings = settings

    async def search(self, workspace_id: uuid.UUID, request: SearchRequest) -> SearchResponse:
        try:
            vector = await self._embedder.embed_query(request.query)
        except (EmbeddingError, EmbeddingNotConfiguredError) as exc:
            raise AppError(503, "embeddings_unavailable", str(exc)) from exc
        try:
            chunks = await retrieve(
                self._qdrant,
                vector,
                workspace_id=workspace_id,
                top_k=request.top_k or self._settings.retrieval_top_k,
                score_threshold=self._settings.retrieval_score_threshold,
                document_ids=request.document_ids,
            )
        except VectorIndexError as exc:
            raise AppError(503, "index_unavailable", str(exc)) from exc
        return SearchResponse(
            results=[
                SearchResult(
                    document_id=chunk.document_id,
                    filename=chunk.filename,
                    page=chunk.page,
                    chunk_index=chunk.chunk_index,
                    score=chunk.score,
                    snippet=make_snippet(chunk.text),
                )
                for chunk in chunks
            ]
        )
