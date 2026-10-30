"""Grounded chat (BUILD.md section 6, query path)."""

import uuid
from datetime import timedelta

from app.ai.embeddings import EmbeddingError, EmbeddingNotConfiguredError
from app.ai.llm import (
    LLM,
    LLMError,
    LLMMessage,
    LLMNotConfiguredError,
    LLMRateLimitedError,
    LLMResult,
)
from app.ai.retrieval import KnowledgeRetriever, RetrievedChunk
from app.core.config import Settings
from app.core.errors import AppError
from app.core.pagination import Page, PageParams
from app.db.mongo import Mongo, Session
from app.models import Conversation, Message, User
from app.models.enums import MessageRole
from app.models.records import utcnow
from app.rag.chain import (
    INSUFFICIENT_ANSWER,
    answer_messages,
    number_within_budget,
    resolve_citations,
    rewrite_messages,
)
from app.rag.indexing import VectorIndexError
from app.repositories.activity import ActivityRepository
from app.repositories.conversations import ConversationRepository
from app.schemas.chat import (
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
)

CONVERSATION_NOT_FOUND = AppError(404, "conversation_not_found", "Conversation not found.")
TITLE_LENGTH = 80
REWRITE_MAX_TOKENS = 200
MAX_STANDALONE_QUESTION = 1000


def conversation_title(message: str) -> str:
    title = " ".join(message.split())
    return title if len(title) <= TITLE_LENGTH else title[: TITLE_LENGTH - 1].rstrip() + "…"


async def complete_or_raise(
    llm: LLM, messages: list[LLMMessage], *, max_tokens: int, json_mode: bool = False
) -> LLMResult:
    """Call the model, mapping provider failures to API errors."""
    try:
        return await llm.complete(messages, max_tokens=max_tokens, json_mode=json_mode)
    except LLMRateLimitedError as exc:
        raise AppError(429, "llm_rate_limited", str(exc), headers={"Retry-After": "10"}) from exc
    except (LLMError, LLMNotConfiguredError) as exc:
        raise AppError(503, "llm_unavailable", str(exc)) from exc


async def retrieve_or_raise(
    retriever: KnowledgeRetriever, workspace_id: uuid.UUID, query: str
) -> list[RetrievedChunk]:
    try:
        return await retriever.search(workspace_id, query)
    except (EmbeddingError, EmbeddingNotConfiguredError) as exc:
        raise AppError(503, "embeddings_unavailable", str(exc)) from exc
    except VectorIndexError as exc:
        raise AppError(503, "index_unavailable", str(exc)) from exc


class ChatService:
    def __init__(
        self, mongo: Mongo, retriever: KnowledgeRetriever, llm: LLM, settings: Settings
    ) -> None:
        self._mongo = mongo
        self._retriever = retriever
        self._llm = llm
        self._settings = settings
        self._conversations = ConversationRepository(mongo.db)
        self._activity = ActivityRepository(mongo.db)

    async def send(self, user: User, workspace_id: uuid.UUID, request: ChatRequest) -> ChatResponse:
        if request.conversation_id is not None:
            existing = await self._conversations.get(workspace_id, user.id, request.conversation_id)
            if existing is None:
                raise CONVERSATION_NOT_FOUND
            conversation = existing
            history = await self._conversations.recent_messages(
                conversation, self._settings.chat_history_messages
            )
        else:
            conversation = Conversation(
                workspace_id=workspace_id,
                user_id=user.id,
                title=conversation_title(request.message),
            )
            history = []

        prompt_tokens = completion_tokens = 0
        question = request.message
        if history:
            rewrite = await complete_or_raise(
                self._llm,
                rewrite_messages([(m.role.value, m.content) for m in history], request.message),
                max_tokens=REWRITE_MAX_TOKENS,
            )
            prompt_tokens += rewrite.prompt_tokens
            completion_tokens += rewrite.completion_tokens
            question = rewrite.text[:MAX_STANDALONE_QUESTION] or request.message

        chunks = await retrieve_or_raise(self._retriever, workspace_id, question)
        if not chunks:
            # Nothing relevant enough: the fixed answer, without calling the model.
            content, sources, insufficient = INSUFFICIENT_ANSWER, [], True
        else:
            numbered = number_within_budget(chunks, self._settings.context_token_budget)
            result = await complete_or_raise(
                self._llm,
                answer_messages(question, numbered),
                max_tokens=self._settings.llm_max_output_tokens,
            )
            if not result.text:
                raise AppError(503, "llm_unavailable", str(LLMError()))
            prompt_tokens += result.prompt_tokens
            completion_tokens += result.completion_tokens
            content, cited = resolve_citations(result.text, numbered)
            sources = [source.to_document() for source in cited]
            insufficient = False

        asked_at = utcnow()
        # One millisecond apart so the pair always sorts question-then-answer.
        answered_at = asked_at + timedelta(milliseconds=1)
        question_message = Message(
            conversation_id=conversation.id,
            workspace_id=workspace_id,
            role=MessageRole.USER,
            content=request.message,
            created_at=asked_at,
            updated_at=asked_at,
        )
        answer = Message(
            conversation_id=conversation.id,
            workspace_id=workspace_id,
            role=MessageRole.ASSISTANT,
            content=content,
            sources=sources,
            insufficient_context=insufficient,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            created_at=answered_at,
            updated_at=answered_at,
        )

        async def work(session: Session) -> None:
            if request.conversation_id is None:
                conversation.updated_at = answered_at
                await self._conversations.insert(conversation, session)
                await self._activity.record(
                    workspace_id=workspace_id,
                    user_id=user.id,
                    action="conversation.created",
                    entity_type="conversation",
                    entity_id=conversation.id,
                    session=session,
                )
            else:
                await self._conversations.touch(conversation, answered_at, session)
            await self._conversations.insert_messages([question_message, answer], session)
            # No message text in the log: only what happened.
            await self._activity.record(
                workspace_id=workspace_id,
                user_id=user.id,
                action="chat.answered",
                entity_type="conversation",
                entity_id=conversation.id,
                details={"sources": len(sources), "insufficient_context": insufficient},
                session=session,
            )

        await self._mongo.transaction(work)
        return ChatResponse(conversation_id=conversation.id, message=ChatMessageOut.build(answer))

    async def list_conversations(
        self, user: User, workspace_id: uuid.UUID, params: PageParams
    ) -> Page[ConversationSummary]:
        rows, total = await self._conversations.list_for_user(workspace_id, user.id, params)
        return Page[ConversationSummary].build(
            [ConversationSummary.build(row) for row in rows], total, params
        )

    async def get_conversation(
        self, user: User, workspace_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> ConversationDetail:
        conversation = await self._conversations.get(workspace_id, user.id, conversation_id)
        if conversation is None:
            raise CONVERSATION_NOT_FOUND
        messages = await self._conversations.messages(conversation)
        return ConversationDetail(
            **ConversationSummary.build(conversation).model_dump(),
            messages=[ChatMessageOut.build(message) for message in messages],
        )
