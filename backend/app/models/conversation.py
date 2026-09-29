import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MessageRole, in_check, string_enum


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        # A user's conversations in a workspace, most recently active first.
        Index(
            "ix_conversations_workspace_id_user_id_updated_at",
            "workspace_id",
            "user_id",
            "updated_at",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        in_check("role", MessageRole),
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[MessageRole] = mapped_column(string_enum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(
        default=list, server_default=text("'[]'::jsonb")
    )
    # True when retrieval found nothing above the threshold and the LLM was not called.
    insufficient_context: Mapped[bool] = mapped_column(server_default=false())
    prompt_tokens: Mapped[int] = mapped_column(server_default=text("0"))
    completion_tokens: Mapped[int] = mapped_column(server_default=text("0"))
