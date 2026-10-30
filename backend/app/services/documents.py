import logging
import uuid

from app.core.config import Settings
from app.core.errors import AppError, UserFacingError
from app.core.pagination import Page, PageParams
from app.db.mongo import Mongo, Session
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
        mongo: Mongo,
        settings: Settings,
        storage: Storage,
        queue: JobQueue | None,
        index: VectorIndex,
    ) -> None:
        self._mongo = mongo
        self._settings = settings
        self._storage = storage
        self._queue = queue
        self._index = index
        self._documents = DocumentRepository(mongo.db)
        self._activity = ActivityRepository(mongo.db)

    async def upload(
        self, user: User, workspace_id: uuid.UUID, filename: str | None, data: bytes
    ) -> DocumentOut:
        """Validate, store the file, record it as UPLOADED, and queue processing.

        Extraction, chunking, embedding and indexing happen later in the worker.
        """
        if self._queue is None:
            # No job queue (arq not installed): refuse before storing anything, so no document
            # is left UPLOADED with nothing to process it.
            raise AppError(
                503,
                "processing_unavailable",
                "Document processing is unavailable on this server (background job queue is "
                "not configured).",
            )
        queue = self._queue
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
        )

        async def work(session: Session) -> None:
            await self._documents.insert(document, session)
            await self._activity.record(
                workspace_id=workspace_id,
                user_id=user.id,
                action="document.uploaded",
                entity_type="document",
                entity_id=document.id,
                details={"filename": document.filename},
                session=session,
            )

        try:
            await self._mongo.transaction(work)
        except Exception:
            await self._storage.delete(storage_key)
            raise

        try:
            await queue.enqueue_document_processing(
                ProcessDocumentJob(document_id=document.id, workspace_id=workspace_id)
            )
        except Exception as exc:
            logger.exception("enqueue_failed", extra={"document_id": str(document.id)})
            await self._documents.mark_failed(
                document, "Processing could not be queued. Upload the file again."
            )
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

        async def work(session: Session) -> None:
            await self._documents.delete(document, session)
            await self._activity.record(
                workspace_id=workspace_id,
                user_id=user.id,
                action="document.deleted",
                entity_type="document",
                entity_id=document_id,
                details={"filename": document.filename},
                session=session,
            )

        await self._mongo.transaction(work)
        try:
            await self._storage.delete(document.storage_key)
        except Exception:
            # The record is gone; an orphaned file is harmless and is logged for cleanup.
            logger.exception("stored_file_not_deleted", extra={"document_id": str(document_id)})
