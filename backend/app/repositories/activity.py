import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, count_statement
from app.models import ActivityLog, User


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def record(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None,
        action: str,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Add an entry to the caller's transaction, so it commits (or not) with the change."""
        self._session.add(
            ActivityLog(
                workspace_id=workspace_id,
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
        )

    async def list(
        self, workspace_id: uuid.UUID, params: PageParams
    ) -> tuple[list[tuple[ActivityLog, str | None]], int]:
        statement = (
            select(ActivityLog, User.full_name)
            .outerjoin(User, User.id == ActivityLog.user_id)
            .where(ActivityLog.workspace_id == workspace_id)
            .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        )
        total = await self._session.scalar(count_statement(statement)) or 0
        rows = await self._session.execute(statement.limit(params.page_size).offset(params.offset))
        return [(entry, name) for entry, name in rows.tuples()], total
