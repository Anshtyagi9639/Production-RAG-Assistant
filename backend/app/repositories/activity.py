import uuid
from typing import Any

from app.core.pagination import PageParams
from app.db.mongo import Database, Session
from app.models import ActivityLog
from app.repositories.users import UserRepository


class ActivityRepository:
    def __init__(self, db: Database) -> None:
        self._activity = db["activity_logs"]
        self._users = UserRepository(db)

    async def record(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None,
        action: str,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        session: Session | None = None,
    ) -> None:
        """Add an entry; pass the caller's transaction session so it commits (or not) with the
        change it describes."""
        entry = ActivityLog(
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        await self._activity.insert_one(entry.to_document(), session=session)

    async def list(
        self, workspace_id: uuid.UUID, params: PageParams
    ) -> tuple[list[tuple[ActivityLog, str | None]], int]:
        query = {"workspace_id": workspace_id}
        total = await self._activity.count_documents(query)
        cursor = (
            self._activity.find(query)
            .sort([("created_at", -1), ("_id", -1)])
            .skip(params.offset)
            .limit(params.page_size)
        )
        entries = [ActivityLog.from_document(item) async for item in cursor]
        names = await self._users.names(entry.user_id for entry in entries)
        return [(e, names.get(e.user_id) if e.user_id else None) for e in entries], total
