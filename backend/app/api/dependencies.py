import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Header, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.ai.retrieval import KnowledgeRetriever
from app.core.config import Settings
from app.core.errors import AppError
from app.core.pagination import MAX_PAGE_SIZE, PageParams
from app.core.rate_limit import RateLimiter
from app.core.security import InvalidTokenError, decode_access_token
from app.db.mongo import Mongo
from app.models import User
from app.models.enums import WorkspaceRole
from app.rag.indexing import VectorIndex
from app.repositories.users import UserRepository
from app.repositories.workspaces import Membership, WorkspaceRepository
from app.services.agent import AgentService
from app.services.chat import ChatService
from app.services.documents import DocumentService
from app.services.health import HealthService, mongodb_check, qdrant_check, redis_check
from app.services.search import SearchService

_bearer = HTTPBearer(auto_error=False)
_UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_mongo(request: Request) -> Mongo:
    """The process-wide MongoDB client and database, created in the app lifespan."""
    mongo: Mongo = request.app.state.mongo
    return mongo


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
MongoDep = Annotated[Mongo, Depends(get_mongo)]


async def get_current_user(
    mongo: MongoDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise AppError(
            401, "not_authenticated", "Sign in to continue.", headers=_UNAUTHENTICATED_HEADERS
        )
    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except InvalidTokenError as exc:
        raise AppError(
            401,
            "invalid_token",
            "Your session is invalid or has expired. Sign in again.",
            headers=_UNAUTHENTICATED_HEADERS,
        ) from exc
    user = await UserRepository(mongo.db).get(user_id)
    if user is None or not user.is_active:
        raise AppError(
            401,
            "invalid_token",
            "Your session is no longer valid.",
            headers=_UNAUTHENTICATED_HEADERS,
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_workspace_membership(
    user: CurrentUser,
    mongo: MongoDep,
    x_workspace_id: Annotated[str | None, Header()] = None,
) -> Membership:
    """The tenant-isolation choke point: every workspace-scoped route depends on this.

    The workspace comes from `X-Workspace-Id` and is only accepted if the current user is a
    member. Non-members get 404, so workspace ids can't be probed.
    """
    if not x_workspace_id:
        raise AppError(400, "workspace_required", "The X-Workspace-Id header is required.")
    try:
        workspace_id = uuid.UUID(x_workspace_id)
    except ValueError as exc:
        raise AppError(400, "invalid_workspace_id", "X-Workspace-Id must be a UUID.") from exc
    membership = await WorkspaceRepository(mongo.db).get_membership(user.id, workspace_id)
    if membership is None:
        raise AppError(404, "workspace_not_found", "Workspace not found.")
    return membership


WorkspaceMembership = Annotated[Membership, Depends(get_workspace_membership)]


def require_owner(membership: WorkspaceMembership) -> Membership:
    if membership.role != WorkspaceRole.OWNER:
        raise AppError(403, "owner_required", "Only workspace owners can do this.")
    return membership


OwnerMembership = Annotated[Membership, Depends(require_owner)]


def get_page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


PageParamsDep = Annotated[PageParams, Depends(get_page_params)]


def get_document_service(
    request: Request, mongo: MongoDep, settings: SettingsDep
) -> DocumentService:
    state = request.app.state
    return DocumentService(
        mongo, settings, state.storage, state.job_queue, VectorIndex(state.qdrant)
    )


def get_knowledge_retriever(request: Request, settings: SettingsDep) -> KnowledgeRetriever:
    """The only retrieval path (search, chat): always filtered to one workspace."""
    return KnowledgeRetriever(
        request.app.state.query_embedder,
        request.app.state.qdrant,
        top_k=settings.retrieval_top_k,
        score_threshold=settings.retrieval_score_threshold,
    )


RetrieverDep = Annotated[KnowledgeRetriever, Depends(get_knowledge_retriever)]


def get_search_service(retriever: RetrieverDep) -> SearchService:
    return SearchService(retriever)


def get_chat_service(
    request: Request, mongo: MongoDep, retriever: RetrieverDep, settings: SettingsDep
) -> ChatService:
    return ChatService(mongo, retriever, request.app.state.llm, settings)


def get_agent_service(request: Request, mongo: MongoDep) -> AgentService:
    return AgentService(mongo, request.app.state.job_queue)


def rate_limited(scope: str) -> Callable[..., Awaitable[None]]:
    """Per-user request limit for an expensive route (it calls OpenAI)."""

    async def check(request: Request, user: CurrentUser, settings: SettingsDep) -> None:
        limiter = RateLimiter(
            request.app.state.redis,
            limit=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
        await limiter.check(scope, user.id)

    return check


def get_health_service(request: Request) -> HealthService:
    state = request.app.state
    return HealthService(
        {
            "mongodb": mongodb_check(state.mongo),
            "redis": redis_check(state.redis),
            "qdrant": qdrant_check(state.qdrant),
        },
        timeout_seconds=state.settings.health_check_timeout_seconds,
    )
