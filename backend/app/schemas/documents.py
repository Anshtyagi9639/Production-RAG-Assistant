import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Document
from app.models.enums import DocumentStatus


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    page_count: int | None
    chunk_count: int | None
    uploaded_by_name: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None

    @classmethod
    def build(cls, document: Document, uploaded_by_name: str | None) -> "DocumentOut":
        return cls(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            status=document.status,
            error_message=document.error_message,
            page_count=document.page_count,
            chunk_count=document.chunk_count,
            uploaded_by_name=uploaded_by_name,
            created_at=document.created_at,
            updated_at=document.updated_at,
            processed_at=document.processed_at,
        )


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    document_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)


class SearchResult(BaseModel):
    document_id: uuid.UUID
    filename: str
    page: int | None
    chunk_index: int
    score: float
    snippet: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
