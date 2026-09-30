import uuid
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, apply_sort, count_statement
from app.models import Document, User
from app.models.enums import DocumentStatus

DocumentRow = tuple[Document, str | None]

SORTABLE = {"created_at": Document.created_at, "filename": Document.filename}


def _with_uploader(workspace_id: uuid.UUID) -> Select[Any]:
    return (
        select(Document, User.full_name)
        .outerjoin(User, User.id == Document.uploaded_by_id)
        .where(Document.workspace_id == workspace_id)
    )


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, document: Document) -> None:
        self._session.add(document)

    async def list(
        self,
        workspace_id: uuid.UUID,
        params: PageParams,
        sort: str,
        status: DocumentStatus | None,
    ) -> tuple[list[DocumentRow], int]:
        statement = _with_uploader(workspace_id)
        if status is not None:
            statement = statement.where(Document.status == status)
        statement = apply_sort(statement, sort, SORTABLE, Document.id)
        total = await self._session.scalar(count_statement(statement)) or 0
        rows = await self._session.execute(statement.limit(params.page_size).offset(params.offset))
        return [(document, name) for document, name in rows.tuples()], total

    async def get(self, workspace_id: uuid.UUID, document_id: uuid.UUID) -> DocumentRow | None:
        row = (
            await self._session.execute(
                _with_uploader(workspace_id).where(Document.id == document_id)
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def delete(self, document: Document) -> None:
        # document_chunks rows go with it (ON DELETE CASCADE).
        await self._session.delete(document)
