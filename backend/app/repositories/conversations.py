import uuid
from datetime import datetime

from app.core.pagination import PageParams
from app.db.mongo import Database, Session
from app.models import Conversation, Message


class ConversationRepository:
    """Conversations are private to their creator: every lookup is scoped to the workspace
    and the user, so another member (or workspace) gets nothing back."""

    def __init__(self, db: Database) -> None:
        self._conversations = db["conversations"]
        self._messages = db["messages"]

    def _scope(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, uuid.UUID]:
        return {"workspace_id": workspace_id, "user_id": user_id}

    async def get(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> Conversation | None:
        document = await self._conversations.find_one(
            {"_id": conversation_id, **self._scope(workspace_id, user_id)}
        )
        return Conversation.from_document(document) if document else None

    async def list_for_user(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, params: PageParams
    ) -> tuple[list[Conversation], int]:
        query = self._scope(workspace_id, user_id)
        total = await self._conversations.count_documents(query)
        cursor = (
            self._conversations.find(query)
            .sort([("updated_at", -1), ("_id", -1)])
            .skip(params.offset)
            .limit(params.page_size)
        )
        return [Conversation.from_document(item) async for item in cursor], total

    async def insert(self, conversation: Conversation, session: Session) -> None:
        await self._conversations.insert_one(conversation.to_document(), session=session)

    async def touch(self, conversation: Conversation, at: datetime, session: Session) -> None:
        await self._conversations.update_one(
            {"_id": conversation.id, "workspace_id": conversation.workspace_id},
            {"$set": {"updated_at": at}},
            session=session,
        )

    async def insert_messages(self, messages: list[Message], session: Session) -> None:
        await self._messages.insert_many([m.to_document() for m in messages], session=session)

    async def messages(self, conversation: Conversation) -> list[Message]:
        cursor = self._messages.find(
            {"conversation_id": conversation.id, "workspace_id": conversation.workspace_id}
        ).sort([("created_at", 1), ("_id", 1)])
        return [Message.from_document(item) async for item in cursor]

    async def recent_messages(self, conversation: Conversation, limit: int) -> list[Message]:
        """The last `limit` messages, oldest first."""
        if limit == 0:
            return []
        cursor = (
            self._messages.find(
                {"conversation_id": conversation.id, "workspace_id": conversation.workspace_id}
            )
            .sort([("created_at", -1), ("_id", -1)])
            .limit(limit)
        )
        latest = [Message.from_document(item) async for item in cursor]
        return latest[::-1]
