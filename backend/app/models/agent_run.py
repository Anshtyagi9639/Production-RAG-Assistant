import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AgentRunStatus, in_check, string_enum


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        in_check("status", AgentRunStatus),
        Index("ix_agent_runs_workspace_id_created_at", "workspace_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    # SET NULL keeps the run (and its token usage) in workspace stats if the user is deleted.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    request: Mapped[str] = mapped_column(Text)
    status: Mapped[AgentRunStatus] = mapped_column(
        string_enum(AgentRunStatus), server_default=AgentRunStatus.QUEUED.value
    )
    classification: Mapped[str | None] = mapped_column(String(20))
    # One entry per executed node: name, status, timings, summary.
    trace: Mapped[list[dict[str, Any]]] = mapped_column(
        default=list, server_default=text("'[]'::jsonb")
    )
    final_answer: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(
        default=list, server_default=text("'[]'::jsonb")
    )
    # True when validation still failed after one revision.
    is_partial: Mapped[bool] = mapped_column(server_default=false())
    prompt_tokens: Mapped[int] = mapped_column(server_default=text("0"))
    completion_tokens: Mapped[int] = mapped_column(server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
