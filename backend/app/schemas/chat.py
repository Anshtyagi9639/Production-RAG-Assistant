import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import AgentRun, Conversation, Message
from app.models.enums import AgentRunStatus

MAX_MESSAGE_LENGTH = 4000


class SourceOut(BaseModel):
    """A passage an answer cites. `index` is the [n] used in the answer text."""

    index: int
    document_id: uuid.UUID
    filename: str
    page: int | None
    chunk_index: int
    score: float
    snippet: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    conversation_id: uuid.UUID | None = None


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[SourceOut]
    # True when no passage passed the threshold and the fixed answer was returned (no LLM call).
    insufficient_context: bool
    created_at: datetime

    @classmethod
    def build(cls, message: Message) -> "ChatMessageOut":
        return cls(
            id=message.id,
            role=message.role.value,
            content=message.content,
            sources=[SourceOut.model_validate(source) for source in message.sources],
            insufficient_context=message.insufficient_context,
            created_at=message.created_at,
        )


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: ChatMessageOut


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def build(cls, conversation: Conversation) -> "ConversationSummary":
        return cls(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )


class ConversationDetail(ConversationSummary):
    messages: list[ChatMessageOut]


class AgentRunRequest(BaseModel):
    request: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class AgentStepOut(BaseModel):
    node: str
    status: Literal["completed", "failed"]
    started_at: datetime
    duration_ms: int
    summary: str


class AgentRunOut(BaseModel):
    id: uuid.UUID
    request: str
    status: AgentRunStatus
    classification: Literal["simple", "complex"] | None
    trace: list[AgentStepOut]
    final_answer: str | None
    sources: list[SourceOut]
    is_partial: bool
    error: str | None
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def build(cls, run: AgentRun) -> "AgentRunOut":
        classification: Any = run.classification
        return cls(
            id=run.id,
            request=run.request,
            status=run.status,
            classification=classification,
            trace=[AgentStepOut.model_validate(step) for step in run.trace],
            final_answer=run.final_answer,
            sources=[SourceOut.model_validate(source) for source in run.sources],
            is_partial=run.is_partial,
            error=run.error,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )
