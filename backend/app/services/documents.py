import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, UserFacingError
from app.core.pagination import Page, PageParams
from app.models import Document, User
from app.models.enums import DocumentStatus
from app.rag.indexing import VectorIndex
from app.repositories.activity import ActivityRepository
from app.repositories.documents import DocumentRepository
from app.schemas.documents import DocumentOut
from app.services.queue import JobQueue, ProcessDocumentJob
from app.services.uploads import validate_upload
from app.storage.base import Storage

logger = logging.getLogger(__name__)

DOCUMENT_NOT_FOUND = AppError(404, "document_not_found", "Document not found.")


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        storage: Storage,
        queue: JobQueue,
        index: VectorIndex,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._queue = queue
        self._index = index
        self._documents = DocumentRepository(session)
        self._activity = ActivityRepository(session)

    async def upload(
        self, user: User, workspace_id: uuid.UUID, filename: str | None, data: bytes
    ) -> DocumentOut:
        """Validate, store the file, record it as UPLOADED, and queue processing.

        Extraction, chunking, embedding and indexing happen later in the worker.
        """
        upload = validate_upload(filename, data, self._settings.max_upload_bytes)
        # The stored name is random: user-supplied names never reach the filesystem or bucket.
        storage_key = f"{uuid.uuid4().hex}{upload.extension}"
        await self._storage.save(storage_key, upload.data)

        document = Document(
            workspace_id=workspace_id,
            uploaded_by_id=user.id,
            filename=upload.filename,
            storage_key=storage_key,
            content_type=upload.content_type,
            size_bytes=len(upload.data),
            status=DocumentStatus.UPLOADED,
        )
        try:
            self._documents.add(document)
            await self._session.flush()
            self._activity.record(
                workspace_id=workspace_id,
                user_id=user.id,
                action="document.uploaded",
                entity_type="document",
                entity_id=document.id,
                details={"filename": document.filename},
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            await self._storage.delete(storage_key)
            raise
        await self._session.refresh(document)

        try:
            await self._queue.enqueue_document_processing(
                ProcessDocumentJob(document_id=document.id, workspace_id=workspace_id)
            )
        except Exception as exc:
            logger.exception("enqueue_failed", extra={"document_id": str(document.id)})
            document.status = DocumentStatus.FAILED
            document.error_message = "Processing could not be queued. Upload the file again."
            await self._session.commit()
            raise AppError(
                503, "queue_unavailable", "The processing queue is unavailable. Try again later."
            ) from exc
        return DocumentOut.build(document, user.full_name)

    async def list(
        self,
        workspace_id: uuid.UUID,
        params: PageParams,
        sort: str,
        status: DocumentStatus | None,
    ) -> Page[DocumentOut]:
        rows, total = await self._documents.list(workspace_id, params, sort, status)
        return Page[DocumentOut].build(
            [DocumentOut.build(document, name) for document, name in rows], total, params
        )

    async def get(self, workspace_id: uuid.UUID, document_id: uuid.UUID) -> DocumentOut:
        row = await self._documents.get(workspace_id, document_id)
        if row is None:
            raise DOCUMENT_NOT_FOUND
        return DocumentOut.build(*row)

    async def delete(self, user: User, workspace_id: uuid.UUID, document_id: uuid.UUID) -> None:
        """Remove vectors first: if that fails nothing is deleted, so no document can linger
        in search results after the user was told it's gone."""
        row = await self._documents.get(workspace_id, document_id)
        if row is None:
            raise DOCUMENT_NOT_FOUND
        document = row[0]
        try:
            await self._index.delete_document(document.id, workspace_id)
        except UserFacingError as exc:
            raise AppError(
                503, "index_unavailable", "The search index is unavailable. Try again later."
            ) from exc

        storage_key, filename = document.storage_key, document.filename
        await self._documents.delete(document)
        self._activity.record(
            workspace_id=workspace_id,
            user_id=user.id,
            action="document.deleted",
            entity_type="document",
            entity_id=document_id,
            details={"filename": filename},
        )
        await self._session.commit()
        try:
            await self._storage.delete(storage_key)
        except Exception:
            # The row is gone; an orphaned file is harmless and is logged for cleanup.
            logger.exception("stored_file_not_deleted", extra={"document_id": str(document_id)})
