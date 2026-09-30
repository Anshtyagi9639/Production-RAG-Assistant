import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import DocumentStatus


class ActivityOut(BaseModel):
    id: uuid.UUID
    action: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    details: dict[str, Any] | None
    # None for events without a user (e.g. the worker finished processing) or a deleted user.
    user_name: str | None
    created_at: datetime


class DocumentStats(BaseModel):
    total: int
    by_status: dict[DocumentStatus, int]


class TokenStats(BaseModel):
    prompt: int
    completion: int
    total: int


class StatsOut(BaseModel):
    documents: DocumentStats
    conversations: int
    agent_runs: int
    tokens: TokenStats
