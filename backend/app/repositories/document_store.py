from datetime import UTC, datetime
from typing import Any

from pymongo import ReturnDocument

from app.db.mongo import Mongo, Session
from app.models import ActivityLog
from app.models.enums import DocumentStatus
from app.rag.chunking import Chunk
from app.services.document_processing import ClaimedDocument
from app.services.queue import ProcessDocumentJob

MAX_REASON_LENGTH = 1000


def _now() -> datetime:
    return datetime.now(UTC)


class MongoDocumentStore:
    """The worker's status transitions in MongoDB.

    `claim` is a single atomic find-and-update; `complete` and `fail` are transactions, so a
    concurrent delete or a duplicate job can't interleave with a transition.
    """

    def __init__(self, mongo: Mongo) -> None:
        self._mongo = mongo
        self._documents = mongo.db["documents"]
        self._chunks = mongo.db["document_chunks"]
        self._activity = mongo.db["activity_logs"]

    async def claim(self, job: ProcessDocumentJob) -> ClaimedDocument | None:
        # PROCESSING is claimable so a job retried after a worker crash can finish.
        document = await self._documents.find_one_and_update(
            {
                "_id": job.document_id,
                "workspace_id": job.workspace_id,
                "status": {"$in": [DocumentStatus.UPLOADED.value, DocumentStatus.PROCESSING.value]},
            },
            {
                "$set": {
                    "status": DocumentStatus.PROCESSING.value,
                    "error_message": None,
                    "updated_at": _now(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            return None
        return ClaimedDocument(
            id=document["_id"],
            workspace_id=document["workspace_id"],
            filename=document["filename"],
            storage_key=document["storage_key"],
            created_at=document["created_at"],
        )

    def _activity_entry(
        self, document: ClaimedDocument, action: str, details: dict[str, Any]
    ) -> dict[str, Any]:
        return ActivityLog(
            workspace_id=document.workspace_id,
            user_id=None,
            action=action,
            entity_type="document",
            entity_id=document.id,
            details=details,
        ).to_document()

    async def complete(
        self, document: ClaimedDocument, chunks: list[Chunk], page_count: int | None
    ) -> bool:
        async def work(session: Session) -> bool:
            now = _now()
            result = await self._documents.update_one(
                {"_id": document.id, "workspace_id": document.workspace_id},
                {
                    "$set": {
                        "status": DocumentStatus.COMPLETED.value,
                        "error_message": None,
                        "page_count": page_count,
                        "chunk_count": len(chunks),
                        "processed_at": now,
                        "updated_at": now,
                    }
                },
                session=session,
            )
            if result.matched_count == 0:
                return False  # deleted while processing
            await self._chunks.delete_many({"document_id": document.id}, session=session)
            if chunks:
                await self._chunks.insert_many(
                    [
                        {
                            "_id": chunk.id,
                            "document_id": document.id,
                            "workspace_id": document.workspace_id,
                            "chunk_index": chunk.index,
                            "page": chunk.page,
                            "text": chunk.text,
                            "token_count": chunk.token_count,
                            "created_at": now,
                            "updated_at": now,
                        }
                        for chunk in chunks
                    ],
                    session=session,
                )
            await self._activity.insert_one(
                self._activity_entry(
                    document,
                    "document.processed",
                    {"filename": document.filename, "chunks": len(chunks)},
                ),
                session=session,
            )
            return True

        return await self._mongo.transaction(work)

    async def fail(self, document: ClaimedDocument, reason: str) -> None:
        reason = reason[:MAX_REASON_LENGTH]

        async def work(session: Session) -> None:
            now = _now()
            result = await self._documents.update_one(
                {"_id": document.id, "workspace_id": document.workspace_id},
                {
                    "$set": {
                        "status": DocumentStatus.FAILED.value,
                        "error_message": reason,
                        "processed_at": now,
                        "updated_at": now,
                    }
                },
                session=session,
            )
            if result.matched_count:
                await self._activity.insert_one(
                    self._activity_entry(
                        document,
                        "document.failed",
                        {"filename": document.filename, "reason": reason},
                    ),
                    session=session,
                )

        await self._mongo.transaction(work)
