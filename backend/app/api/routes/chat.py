import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    CurrentUser,
    PageParamsDep,
    WorkspaceMembership,
    get_chat_service,
    rate_limited,
)
from app.core.pagination import Page
from app.schemas.chat import ChatRequest, ChatResponse, ConversationDetail, ConversationSummary
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


@router.post("/chat", dependencies=[Depends(rate_limited("chat"))])
async def chat(
    request: ChatRequest,
    user: CurrentUser,
    membership: WorkspaceMembership,
    service: ChatServiceDep,
) -> ChatResponse:
    """Ask a question about this workspace's documents. Creates a conversation when
    `conversation_id` is omitted. The answer cites its sources as [n]; when nothing relevant is
    found, `insufficient_context` is true and no model call is made."""
    return await service.send(user, membership.workspace.id, request)


@router.get("/conversations")
async def list_conversations(
    user: CurrentUser,
    membership: WorkspaceMembership,
    params: PageParamsDep,
    service: ChatServiceDep,
) -> Page[ConversationSummary]:
    """Your conversations in this workspace, most recently active first."""
    return await service.list_conversations(user, membership.workspace.id, params)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    membership: WorkspaceMembership,
    service: ChatServiceDep,
) -> ConversationDetail:
    return await service.get_conversation(user, membership.workspace.id, conversation_id)
