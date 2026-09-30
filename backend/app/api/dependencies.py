import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.core.pagination import MAX_PAGE_SIZE, PageParams
from app.core.security import InvalidTokenError, decode_access_token
from app.models import User
from app.models.enums import WorkspaceRole
from app.rag.indexing import VectorIndex
from app.repositories.users import UserRepository
from app.repositories.workspaces import Membership, WorkspaceRepository
from app.services.documents import DocumentService
from app.services.health import HealthService, postgres_check, qdrant_check, redis_check
from app.services.search import SearchService

_bearer = HTTPBearer(auto_error=False)
_UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request. Services commit; anything uncommitted is rolled back on close."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    session: SessionDep,
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
    user = await UserRepository(session).get(user_id)
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
    session: SessionDep,
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
    membership = await WorkspaceRepository(session).get_membership(user.id, workspace_id)
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
    request: Request, session: SessionDep, settings: SettingsDep
) -> DocumentService:
    state = request.app.state
    return DocumentService(
        session, settings, state.storage, state.job_queue, VectorIndex(state.qdrant)
    )


def get_search_service(request: Request, settings: SettingsDep) -> SearchService:
    return SearchService(request.app.state.query_embedder, request.app.state.qdrant, settings)


def get_health_service(request: Request) -> HealthService:
    state = request.app.state
    return HealthService(
        {
            "postgres": postgres_check(state.engine),
            "redis": redis_check(state.redis),
            "qdrant": qdrant_check(state.qdrant),
        },
        timeout_seconds=state.settings.health_check_timeout_seconds,
    )
