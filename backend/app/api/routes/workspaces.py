import uuid

from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, MongoDep
from app.schemas.auth import WorkspaceOut
from app.schemas.workspaces import AddMemberRequest, CreateWorkspaceRequest, MemberOut
from app.services.workspaces import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("")
async def list_workspaces(user: CurrentUser, mongo: MongoDep) -> list[WorkspaceOut]:
    return await WorkspaceService(mongo).list_for_user(user)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: CreateWorkspaceRequest, user: CurrentUser, mongo: MongoDep
) -> WorkspaceOut:
    return await WorkspaceService(mongo).create(user, request)


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    workspace_id: uuid.UUID, request: AddMemberRequest, user: CurrentUser, mongo: MongoDep
) -> MemberOut:
    """Owner only. Adds an existing user by email."""
    return await WorkspaceService(mongo).add_member(user, workspace_id, request)
