import uuid

from app.ai.embeddings import EmbeddingError, EmbeddingNotConfiguredError
from app.ai.retrieval import KnowledgeRetriever
from app.core.errors import AppError
from app.rag.chain import make_snippet
from app.rag.indexing import VectorIndexError
from app.schemas.documents import SearchRequest, SearchResponse, SearchResult


class SearchService:
    def __init__(self, retriever: KnowledgeRetriever) -> None:
        self._retriever = retriever

    async def search(self, workspace_id: uuid.UUID, request: SearchRequest) -> SearchResponse:
        try:
            chunks = await self._retriever.search(
                workspace_id, request.query, top_k=request.top_k, document_ids=request.document_ids
            )
        except (EmbeddingError, EmbeddingNotConfiguredError) as exc:
            raise AppError(503, "embeddings_unavailable", str(exc)) from exc
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
