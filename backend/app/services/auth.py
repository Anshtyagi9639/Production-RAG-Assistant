from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.repositories.activity import ActivityRepository
from app.repositories.users import UserRepository
from app.repositories.workspaces import Membership, WorkspaceRepository
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserOut,
    WorkspaceOut,
)

EMAIL_TAKEN = AppError(409, "email_taken", "An account with this email already exists.")


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, full_name=user.full_name, created_at=user.created_at
    )


def workspace_out(membership: Membership) -> WorkspaceOut:
    workspace = membership.workspace
    return WorkspaceOut(
        id=workspace.id, name=workspace.name, role=membership.role, created_at=workspace.created_at
    )


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._activity = ActivityRepository(session)

    async def register(self, request: RegisterRequest) -> RegisterResponse:
        """Create the user, their workspace and the owner membership in one transaction."""
        email = request.email.lower()
        if await self._users.get_by_email(email):
            raise EMAIL_TAKEN
        user = User(
            email=email,
            password_hash=hash_password(request.password),
            full_name=request.full_name.strip(),
        )
        workspace = Workspace(name=f"{user.full_name.split()[0]}'s workspace")
        self._users.add(user)
        self._workspaces.add(workspace)
        await self._session.flush()
        self._workspaces.add_member(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.OWNER)
        )
        self._activity.record(
            workspace_id=workspace.id,
            user_id=user.id,
            action="workspace.created",
            entity_type="workspace",
            entity_id=workspace.id,
            details={"name": workspace.name},
        )
        try:
            await self._session.commit()
        except IntegrityError as exc:
            # Two registrations with the same email raced past the check above.
            await self._session.rollback()
            raise EMAIL_TAKEN from exc
        return RegisterResponse(
            user=user_out(user),
            workspace=workspace_out(Membership(workspace, WorkspaceRole.OWNER)),
        )

    async def login(self, request: LoginRequest) -> TokenResponse:
        user = await self._users.get_by_email(request.email.lower())
        valid = verify_password(request.password, user.password_hash if user else None)
        if user is None or not valid or not user.is_active:
            raise AppError(401, "invalid_credentials", "Incorrect email or password.")
        token, expires_in = create_access_token(user.id, self._settings)
        return TokenResponse(access_token=token, expires_in=expires_in)

    async def me(self, user: User) -> MeResponse:
        memberships = await self._workspaces.list_for_user(user.id)
        return MeResponse(user=user_out(user), workspaces=[workspace_out(m) for m in memberships])
