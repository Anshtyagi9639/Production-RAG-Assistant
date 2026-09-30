from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ActivityLog, Document, DocumentChunk
from app.models.enums import DocumentStatus
from app.rag.chunking import Chunk
from app.services.document_processing import ClaimedDocument
from app.services.queue import ProcessDocumentJob

MAX_REASON_LENGTH = 1000


class SqlDocumentStore:
    """The worker's PostgreSQL status transitions, each in its own short transaction.

    Rows are locked with SELECT ... FOR UPDATE so a concurrent delete or a duplicate job
    can't interleave with a transition.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    async def _locked(
        session: AsyncSession, document: ClaimedDocument | ProcessDocumentJob
    ) -> Document | None:
        document_id = document.id if isinstance(document, ClaimedDocument) else document.document_id
        row: Document | None = await session.scalar(
            select(Document)
            .where(Document.id == document_id, Document.workspace_id == document.workspace_id)
            .with_for_update()
        )
        return row

    async def claim(self, job: ProcessDocumentJob) -> ClaimedDocument | None:
        async with self._session_factory() as session, session.begin():
            document = await self._locked(session, job)
            # PROCESSING is claimable so a job retried after a worker crash can finish.
            if document is None or document.status not in {
                DocumentStatus.UPLOADED,
                DocumentStatus.PROCESSING,
            }:
                return None
            document.status = DocumentStatus.PROCESSING
            document.error_message = None
            return ClaimedDocument(
                id=document.id,
                workspace_id=document.workspace_id,
                filename=document.filename,
                storage_key=document.storage_key,
                created_at=document.created_at,
            )

    async def complete(
        self, document: ClaimedDocument, chunks: list[Chunk], page_count: int | None
    ) -> bool:
        async with self._session_factory() as session, session.begin():
            row = await self._locked(session, document)
            if row is None:
                return False
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
            )
            session.add_all(
                DocumentChunk(
                    id=chunk.id,
                    document_id=document.id,
                    workspace_id=document.workspace_id,
                    chunk_index=chunk.index,
                    page=chunk.page,
                    text=chunk.text,
                    token_count=chunk.token_count,
                )
                for chunk in chunks
            )
            row.status = DocumentStatus.COMPLETED
            row.error_message = None
            row.page_count = page_count
            row.chunk_count = len(chunks)
            row.processed_at = datetime.now(UTC)
            session.add(
                ActivityLog(
                    workspace_id=document.workspace_id,
                    action="document.processed",
                    entity_type="document",
                    entity_id=document.id,
                    details={"filename": document.filename, "chunks": len(chunks)},
                )
            )
            return True

    async def fail(self, document: ClaimedDocument, reason: str) -> None:
        async with self._session_factory() as session, session.begin():
            row = await self._locked(session, document)
            if row is None:
                return
            row.status = DocumentStatus.FAILED
            row.error_message = reason[:MAX_REASON_LENGTH]
            row.processed_at = datetime.now(UTC)
            session.add(
                ActivityLog(
                    workspace_id=document.workspace_id,
                    action="document.failed",
                    entity_type="document",
                    entity_id=document.id,
                    details={"filename": document.filename, "reason": row.error_message},
                )
            )
