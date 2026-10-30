import uuid

from pymongo.errors import DuplicateKeyError

from app.core.errors import AppError
from app.db.mongo import Mongo, Session
from app.models import User, Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.repositories.activity import ActivityRepository
from app.repositories.users import UserRepository
from app.repositories.workspaces import Membership, WorkspaceRepository
from app.schemas.auth import WorkspaceOut
from app.schemas.workspaces import AddMemberRequest, CreateWorkspaceRequest, MemberOut
from app.services.auth import workspace_out

ALREADY_MEMBER = AppError(409, "already_member", "This user is already a member of the workspace.")


class WorkspaceService:
    def __init__(self, mongo: Mongo) -> None:
        self._mongo = mongo
        self._users = UserRepository(mongo.db)
        self._workspaces = WorkspaceRepository(mongo.db)
        self._activity = ActivityRepository(mongo.db)

    async def list_for_user(self, user: User) -> list[WorkspaceOut]:
        return [workspace_out(m) for m in await self._workspaces.list_for_user(user.id)]

    async def create(self, user: User, request: CreateWorkspaceRequest) -> WorkspaceOut:
        workspace = Workspace(name=request.name.strip())

        async def work(session: Session) -> None:
            await self._workspaces.insert(workspace, session)
            await self._workspaces.insert_member(
                WorkspaceMember(
                    workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.OWNER
                ),
                session,
            )
            await self._activity.record(
                workspace_id=workspace.id,
                user_id=user.id,
                action="workspace.created",
                entity_type="workspace",
                entity_id=workspace.id,
                details={"name": workspace.name},
                session=session,
            )

        await self._mongo.transaction(work)
        return workspace_out(Membership(workspace, WorkspaceRole.OWNER))

    async def add_member(
        self, actor: User, workspace_id: uuid.UUID, request: AddMemberRequest
    ) -> MemberOut:
        """Owner only. The user being added must already have an account."""
        membership = await self._workspaces.get_membership(actor.id, workspace_id)
        if membership is None:
            raise AppError(404, "workspace_not_found", "Workspace not found.")
        if membership.role != WorkspaceRole.OWNER:
            raise AppError(403, "owner_required", "Only workspace owners can do this.")
        user = await self._users.get_by_email(request.email.lower())
        if user is None:
            raise AppError(404, "user_not_found", "No account exists with this email.")

        async def work(session: Session) -> None:
            if await self._workspaces.is_member(workspace_id, user.id, session):
                raise ALREADY_MEMBER
            await self._workspaces.insert_member(
                WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=request.role),
                session,
            )
            await self._activity.record(
                workspace_id=workspace_id,
                user_id=actor.id,
                action="member.added",
                entity_type="user",
                entity_id=user.id,
                details={"email": user.email, "role": request.role.value},
                session=session,
            )

        try:
            await self._mongo.transaction(work)
        except DuplicateKeyError as exc:
            raise ALREADY_MEMBER from exc
        return MemberOut(
            user_id=user.id, email=user.email, full_name=user.full_name, role=request.role
        )
