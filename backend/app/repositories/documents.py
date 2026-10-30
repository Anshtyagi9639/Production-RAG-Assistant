import uuid
from typing import Any

from app.core.pagination import PageParams, sort_spec
from app.db.mongo import Database, Session
from app.models import Document
from app.models.enums import DocumentStatus
from app.models.records import utcnow
from app.repositories.users import UserRepository

DocumentRow = tuple[Document, str | None]

SORTABLE = {"created_at": "created_at", "filename": "filename"}


class DocumentRepository:
    def __init__(self, db: Database) -> None:
        self._documents = db["documents"]
        self._chunks = db["document_chunks"]
        self._users = UserRepository(db)

    async def insert(self, document: Document, session: Session | None = None) -> None:
        await self._documents.insert_one(document.to_document(), session=session)

    async def mark_failed(self, document: Document, reason: str) -> None:
        document.status = DocumentStatus.FAILED
        document.error_message = reason
        document.updated_at = utcnow()
        await self._documents.update_one(
            {"_id": document.id, "workspace_id": document.workspace_id},
            {
                "$set": {
                    "status": document.status.value,
                    "error_message": reason,
                    "updated_at": document.updated_at,
                }
            },
        )

    async def list(
        self,
        workspace_id: uuid.UUID,
        params: PageParams,
        sort: str,
        status: DocumentStatus | None,
    ) -> tuple[list[DocumentRow], int]:
        query: dict[str, Any] = {"workspace_id": workspace_id}
        if status is not None:
            query["status"] = status.value
        order = sort_spec(sort, SORTABLE)
        total = await self._documents.count_documents(query)
        cursor = self._documents.find(query).sort(order).skip(params.offset).limit(params.page_size)
        documents = [Document.from_document(item) async for item in cursor]
        names = await self._users.names(d.uploaded_by_id for d in documents)
        return [
            (d, names.get(d.uploaded_by_id) if d.uploaded_by_id else None) for d in documents
        ], total

    async def get(self, workspace_id: uuid.UUID, document_id: uuid.UUID) -> DocumentRow | None:
        item = await self._documents.find_one({"_id": document_id, "workspace_id": workspace_id})
        if item is None:
            return None
        document = Document.from_document(item)
        names = await self._users.names([document.uploaded_by_id])
        return document, names.get(document.uploaded_by_id) if document.uploaded_by_id else None

    async def delete(self, document: Document, session: Session) -> None:
        """Delete the document and its chunks (the former ON DELETE CASCADE), in the caller's
        transaction."""
        await self._chunks.delete_many(
            {"document_id": document.id, "workspace_id": document.workspace_id}, session=session
        )
        await self._documents.delete_one(
            {"_id": document.id, "workspace_id": document.workspace_id}, session=session
        )
