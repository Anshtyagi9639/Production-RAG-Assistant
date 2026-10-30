"""Application records stored in MongoDB. `id` maps to the document's `_id` (a UUID)."""

import uuid
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self, get_type_hints

from app.models.enums import AgentRunStatus, DocumentStatus, MessageRole, WorkspaceRole


def utcnow() -> datetime:
    # MongoDB stores milliseconds; trimming keeps in-memory values equal to what is read back.
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


@dataclass(kw_only=True)
class Record:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            document["_id" if item.name == "id" else item.name] = (
                value.value if isinstance(value, StrEnum) else value
            )
        return document

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> Self:
        hints = get_type_hints(cls)
        values: dict[str, Any] = {}
        for item in fields(cls):
            raw = document.get("_id" if item.name == "id" else item.name)
            hint = hints[item.name]
            if isinstance(hint, type) and issubclass(hint, StrEnum) and raw is not None:
                raw = hint(raw)
            values[item.name] = raw
        return cls(**values)


@dataclass(kw_only=True)
class User(Record):
    email: str
    # None only for accounts imported from fixtures before the seed script set a password.
    password_hash: str | None
    full_name: str
    is_active: bool = True


@dataclass(kw_only=True)
class Workspace(Record):
    name: str


@dataclass(kw_only=True)
class WorkspaceMember(Record):
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: WorkspaceRole


@dataclass(kw_only=True)
class Document(Record):
    workspace_id: uuid.UUID
    uploaded_by_id: uuid.UUID | None
    filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    status: DocumentStatus = DocumentStatus.UPLOADED
    error_message: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    processed_at: datetime | None = None


@dataclass(kw_only=True)
class ActivityLog(Record):
    workspace_id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    details: dict[str, Any] | None = None


@dataclass(kw_only=True)
class Conversation(Record):
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    title: str


@dataclass(kw_only=True)
class Message(Record):
    conversation_id: uuid.UUID
    # Denormalized from the conversation: tenant filters and token totals need no lookup.
    workspace_id: uuid.UUID
    role: MessageRole
    content: str
    # Citations as stored by app.rag.chain.NumberedSource.to_document.
    sources: list[dict[str, Any]] = field(default_factory=list)
    insufficient_context: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(kw_only=True)
class AgentRun(Record):
    workspace_id: uuid.UUID
    user_id: uuid.UUID | None
    request: str
    status: AgentRunStatus = AgentRunStatus.QUEUED
    classification: str | None = None
    # One entry per executed graph node: node, status, started_at, duration_ms, summary.
    trace: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    is_partial: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
