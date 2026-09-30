import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, Conversation, Document, Message
from app.models.enums import DocumentStatus


class StatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def documents_by_status(self, workspace_id: uuid.UUID) -> dict[DocumentStatus, int]:
        rows = await self._session.execute(
            select(Document.status, func.count())
            .where(Document.workspace_id == workspace_id)
            .group_by(Document.status)
        )
        counts = dict.fromkeys(DocumentStatus, 0)
        counts.update(dict(rows.tuples().all()))
        return counts

    async def conversation_count(self, workspace_id: uuid.UUID) -> int:
        return (
            await self._session.scalar(
                select(func.count())
                .select_from(Conversation)
                .where(Conversation.workspace_id == workspace_id)
            )
            or 0
        )

    async def agent_run_count(self, workspace_id: uuid.UUID) -> int:
        return (
            await self._session.scalar(
                select(func.count())
                .select_from(AgentRun)
                .where(AgentRun.workspace_id == workspace_id)
            )
            or 0
        )

    async def token_totals(self, workspace_id: uuid.UUID) -> tuple[int, int]:
        """(prompt, completion) tokens across chat messages and agent runs in the workspace."""
        chat = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(Message.prompt_tokens), 0),
                    func.coalesce(func.sum(Message.completion_tokens), 0),
                )
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(Conversation.workspace_id == workspace_id)
            )
        ).one()
        agent = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(AgentRun.prompt_tokens), 0),
                    func.coalesce(func.sum(AgentRun.completion_tokens), 0),
                ).where(AgentRun.workspace_id == workspace_id)
            )
        ).one()
        return int(chat[0]) + int(agent[0]), int(chat[1]) + int(agent[1])
