"""Background processing of one uploaded document:

claim (UPLOADED -> PROCESSING) -> read file -> extract -> clean + chunk -> embed -> index in
Qdrant -> save chunks and mark COMPLETED. Any failure marks the document FAILED with a
readable reason, so a document is never left in PROCESSING by a handled error.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Protocol

from app.ai.embeddings import Embedder, embed_in_batches
from app.core.errors import UserFacingError
from app.rag.chunking import Chunk, chunk_pages
from app.rag.extraction import extract
from app.rag.indexing import VectorIndex
from app.services.queue import ProcessDocumentJob
from app.storage.base import Storage

logger = logging.getLogger(__name__)

INTERNAL_FAILURE_REASON = "Processing failed because of an internal error. Try uploading again."


class Outcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ClaimedDocument:
    id: uuid.UUID
    workspace_id: uuid.UUID
    filename: str
    storage_key: str
    created_at: datetime

    @property
    def extension(self) -> str:
        return PurePosixPath(self.storage_key).suffix


class DocumentStore(Protocol):
    """Status transitions for the worker. Each method is its own transaction."""

    async def claim(self, job: ProcessDocumentJob) -> ClaimedDocument | None:
        """Move the document to PROCESSING. None if it doesn't exist in the job's workspace or
        is not waiting to be processed (already COMPLETED or FAILED)."""
        ...

    async def complete(
        self, document: ClaimedDocument, chunks: list[Chunk], page_count: int | None
    ) -> bool:
        """Save chunks and mark COMPLETED. False if the document was deleted meanwhile."""
        ...

    async def fail(self, document: ClaimedDocument, reason: str) -> None: ...


class DocumentProcessor:
    def __init__(
        self,
        *,
        store: DocumentStore,
        storage: Storage,
        embedder: Embedder,
        index: VectorIndex,
        embedding_batch_size: int,
        embedding_max_attempts: int,
    ) -> None:
        self._store = store
        self._storage = storage
        self._embedder = embedder
        self._index = index
        self._batch_size = embedding_batch_size
        self._max_attempts = embedding_max_attempts

    async def process(self, job: ProcessDocumentJob) -> Outcome:
        document = await self._store.claim(job)
        if document is None:
            logger.info("document_job_skipped", extra={"document_id": str(job.document_id)})
            return Outcome.SKIPPED

        log_context = {"document_id": str(document.id), "workspace_id": str(document.workspace_id)}
        indexed = False
        try:
            data = await self._storage.read(document.storage_key)
            extracted = await asyncio.to_thread(extract, data, document.extension)
            chunks = await asyncio.to_thread(chunk_pages, extracted.pages, document.id)
            vectors = await embed_in_batches(
                self._embedder,
                [chunk.text for chunk in chunks],
                batch_size=self._batch_size,
                max_attempts=self._max_attempts,
            )
            await self._index.replace_document(
                document_id=document.id,
                workspace_id=document.workspace_id,
                filename=document.filename,
                created_at=document.created_at,
                chunks=chunks,
                vectors=vectors,
            )
            indexed = True
            if not await self._store.complete(document, chunks, extracted.page_count):
                # Deleted while we were working: don't leave its vectors searchable.
                await self._index.delete_document(document.id, document.workspace_id)
                logger.info("document_deleted_during_processing", extra=log_context)
                return Outcome.SKIPPED
        except Exception as exc:
            if isinstance(exc, UserFacingError):
                reason = str(exc)
                logger.warning(
                    "document_processing_failed", extra={**log_context, "reason": reason}
                )
            else:
                reason = INTERNAL_FAILURE_REASON
                logger.exception("document_processing_error", extra=log_context)
            if indexed:
                await self._remove_vectors(document)
            # If this raises (e.g. the database is down), the job fails and arq retries it.
            await self._store.fail(document, reason)
            return Outcome.FAILED

        logger.info("document_processed", extra={**log_context, "chunks": len(chunks)})
        return Outcome.COMPLETED

    async def _remove_vectors(self, document: ClaimedDocument) -> None:
        try:
            await self._index.delete_document(document.id, document.workspace_id)
        except UserFacingError:
            logger.warning("orphan_vectors_not_removed", extra={"document_id": str(document.id)})
