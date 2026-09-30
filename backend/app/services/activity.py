import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PageParams
from app.repositories.activity import ActivityRepository
from app.repositories.stats import StatsRepository
from app.schemas.activity import ActivityOut, DocumentStats, StatsOut, TokenStats


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self._activity = ActivityRepository(session)
        self._stats = StatsRepository(session)

    async def list(self, workspace_id: uuid.UUID, params: PageParams) -> Page[ActivityOut]:
        rows, total = await self._activity.list(workspace_id, params)
        items = [
            ActivityOut(
                id=entry.id,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                details=entry.details,
                user_name=user_name,
                created_at=entry.created_at,
            )
            for entry, user_name in rows
        ]
        return Page[ActivityOut].build(items, total, params)

    async def stats(self, workspace_id: uuid.UUID) -> StatsOut:
        by_status = await self._stats.documents_by_status(workspace_id)
        prompt, completion = await self._stats.token_totals(workspace_id)
        return StatsOut(
            documents=DocumentStats(total=sum(by_status.values()), by_status=by_status),
            conversations=await self._stats.conversation_count(workspace_id),
            agent_runs=await self._stats.agent_run_count(workspace_id),
            tokens=TokenStats(prompt=prompt, completion=completion, total=prompt + completion),
        )
