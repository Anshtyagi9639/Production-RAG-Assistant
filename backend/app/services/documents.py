import logging
import uuid

from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.errors import AppError, UserFacingError
from app.core.pagination import Page, PageParams
from app.core.security import (
    ExpiredTokenError,
    InvalidTokenError,
    UploadTicket,
    create_upload_token,
    decode_upload_token,
)
from app.db.mongo import Mongo, Session
from app.models import Document, User
from app.models.enums import DocumentStatus
from app.rag.indexing import VectorIndex
from app.repositories.activity import ActivityRepository
from app.repositories.documents import DocumentRepository
from app.schemas.documents import DirectUploadOut, DocumentOut
from app.services.queue import JobQueue, ProcessDocumentJob
from app.services.uploads import (
    HEAD_SAMPLE_BYTES,
    validate_filename,
    validate_head,
    validate_size,
    validate_upload,
)
from app.storage.base import Storage

logger = logging.getLogger(__name__)

DOCUMENT_NOT_FOUND = AppError(404, "document_not_found", "Document not found.")
INVALID_UPLOAD = AppError(400, "invalid_upload", "This upload is not valid. Upload the file again.")
UPLOAD_EXPIRED = AppError(400, "upload_expired", "This upload has expired. Upload the file again.")


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

    def _require_queue(self) -> JobQueue:
        if self._queue is None:
            # No job queue (arq not installed): refuse before storing anything, so no document
            # is left UPLOADED with nothing to process it.
            raise AppError(
                503,
                "processing_unavailable",
                "Document processing is unavailable on this server (background job queue is "
                "not configured).",
            )
        return self._queue

    async def upload(
        self, user: User, workspace_id: uuid.UUID, filename: str | None, data: bytes
    ) -> DocumentOut:
        """Validate, store the file, record it as UPLOADED, and queue processing.

        Extraction, chunking, embedding and indexing happen later in the worker.
        """
        queue = self._require_queue()
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
        try:
            await self._record(user, document)
        except Exception:
            await self._storage.delete(storage_key)
            raise
        await self._enqueue(queue, document)
        return DocumentOut.build(document, user.full_name)

    async def create_direct_upload(
        self, user: User, workspace_id: uuid.UUID, filename: str, size_bytes: int
    ) -> DirectUploadOut:
        """Step 1 of an upload that bypasses the API (which can't take large bodies when it
        runs as a serverless function): check the request and sign a bucket upload for it."""
        self._require_queue()
        name = validate_filename(filename)
        validate_size(size_bytes, self._settings.max_upload_bytes)
        storage_key = f"{uuid.uuid4().hex}{name.extension}"
        expires = self._settings.direct_upload_expire_seconds
        presigned = await self._storage.presign_upload(
            storage_key, name.content_type, size_bytes, expires
        )
        if presigned is None:
            raise AppError(
                409,
                "direct_upload_unavailable",
                "This server takes uploads directly; send the file to /documents/upload.",
            )
        ticket = UploadTicket(user.id, workspace_id, storage_key, name.filename, size_bytes)
        return DirectUploadOut(
            url=presigned.url,
            fields=presigned.fields,
            upload_token=create_upload_token(ticket, expires, self._settings),
            expires_in=expires,
        )

    async def complete_direct_upload(
        self, user: User, workspace_id: uuid.UUID, upload_token: str
    ) -> DocumentOut:
        """Step 2: check the file that reached the bucket, then record and queue it as
        `upload` does. Completing the same upload again returns the same document."""
        queue = self._require_queue()
        try:
            ticket = decode_upload_token(upload_token, self._settings)
        except ExpiredTokenError as exc:
            raise UPLOAD_EXPIRED from exc
        except InvalidTokenError as exc:
            raise INVALID_UPLOAD from exc
        # The ticket is only good for the user and workspace it was issued to.
        if ticket.user_id != user.id or ticket.workspace_id != workspace_id:
            raise INVALID_UPLOAD

        existing = await self._documents.get_by_storage_key(workspace_id, ticket.storage_key)
        if existing is not None:
            return DocumentOut.build(*existing)

        name = validate_filename(ticket.filename)
        size = await self._storage.size(ticket.storage_key)
        if size is None:
            raise AppError(
                409, "upload_incomplete", "The file didn't finish uploading. Upload it again."
            )
        try:
            # The bucket enforced the signed size; checking again costs nothing.
            if size != ticket.size_bytes:
                raise AppError(
                    400, "upload_size_mismatch", "The uploaded file isn't the size that was sent."
                )
            validate_size(size, self._settings.max_upload_bytes)
            head = await self._storage.read_head(ticket.storage_key, HEAD_SAMPLE_BYTES)
            validate_head(name.extension, head, size)
        except AppError:
            await self._storage.delete(ticket.storage_key)
            raise

        document = Document(
            workspace_id=workspace_id,
            uploaded_by_id=user.id,
            filename=name.filename,
            storage_key=ticket.storage_key,
            content_type=name.content_type,
            size_bytes=size,
        )
        try:
            await self._record(user, document)
        except DuplicateKeyError:
            # A concurrent completion of the same upload got there first.
            row = await self._documents.get_by_storage_key(workspace_id, ticket.storage_key)
            if row is None:
                raise
            return DocumentOut.build(*row)
        # On any other failure the file stays: the client may retry while the ticket is valid.
        await self._enqueue(queue, document)
        return DocumentOut.build(document, user.full_name)

    async def _record(self, user: User, document: Document) -> None:
        async def work(session: Session) -> None:
            await self._documents.insert(document, session)
            await self._activity.record(
                workspace_id=document.workspace_id,
                user_id=user.id,
                action="document.uploaded",
                entity_type="document",
                entity_id=document.id,
                details={"filename": document.filename},
                session=session,
            )

        await self._mongo.transaction(work)

    async def _enqueue(self, queue: JobQueue, document: Document) -> None:
        try:
            await queue.enqueue_document_processing(
                ProcessDocumentJob(document_id=document.id, workspace_id=document.workspace_id)
            )
        except Exception as exc:
            logger.exception("enqueue_failed", extra={"document_id": str(document.id)})
            await self._documents.mark_failed(
                document, "Processing could not be queued. Upload the file again."
            )
            raise AppError(
                503, "queue_unavailable", "The processing queue is unavailable. Try again later."
            ) from exc

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
