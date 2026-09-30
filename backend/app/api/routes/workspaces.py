import uuid

from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, SessionDep
from app.schemas.auth import WorkspaceOut
from app.schemas.workspaces import AddMemberRequest, CreateWorkspaceRequest, MemberOut
from app.services.workspaces import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("")
async def list_workspaces(user: CurrentUser, session: SessionDep) -> list[WorkspaceOut]:
    return await WorkspaceService(session).list_for_user(user)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: CreateWorkspaceRequest, user: CurrentUser, session: SessionDep
) -> WorkspaceOut:
    return await WorkspaceService(session).create(user, request)


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    workspace_id: uuid.UUID, request: AddMemberRequest, user: CurrentUser, session: SessionDep
) -> MemberOut:
    """Owner only. Adds an existing user by email."""
    return await WorkspaceService(session).add_member(user, workspace_id, request)
