import logging

from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import email_domain, timed_stage
from app.core.security import create_access_token, hash_password, verify_password
from app.db.mongo import Mongo, Session
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

logger = logging.getLogger(__name__)


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
    def __init__(self, mongo: Mongo, settings: Settings) -> None:
        self._mongo = mongo
        self._settings = settings
        self._users = UserRepository(mongo.db)
        self._workspaces = WorkspaceRepository(mongo.db)
        self._activity = ActivityRepository(mongo.db)

    async def register(self, request: RegisterRequest) -> RegisterResponse:
        """Create the user, their workspace and the owner membership in one transaction."""
        email = request.email.lower()
        op, domain = "auth.register", email_domain(email)
        with timed_stage(logger, op, "password_hash", email_domain=domain):
            password_hash = hash_password(request.password)
        user = User(email=email, password_hash=password_hash, full_name=request.full_name.strip())
        workspace = Workspace(name=f"{user.full_name.split()[0]}'s workspace")

        async def work(session: Session) -> None:
            with timed_stage(logger, op, "email_check", collection="users"):
                if await self._users.get_by_email(email, session):
                    raise EMAIL_TAKEN
            with timed_stage(logger, op, "user_insert", collection="users"):
                await self._users.insert(user, session)
            with timed_stage(logger, op, "workspace_insert", collection="workspaces"):
                await self._workspaces.insert(workspace, session)
            with timed_stage(logger, op, "membership_insert", collection="workspace_members"):
                await self._workspaces.insert_member(
                    WorkspaceMember(
                        workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.OWNER
                    ),
                    session,
                )
            with timed_stage(logger, op, "activity_insert", collection="activity_logs"):
                await self._activity.record(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    action="workspace.created",
                    entity_type="workspace",
                    entity_id=workspace.id,
                    details={"name": workspace.name},
                    session=session,
                )

        try:
            with timed_stage(logger, op, "transaction", email_domain=domain):
                await self._mongo.transaction(work)
        except DuplicateKeyError as exc:
            # Two registrations with the same email raced past the check above; the unique
            # email index rejected the second and the whole transaction rolled back.
            raise EMAIL_TAKEN from exc
        return RegisterResponse(
            user=user_out(user),
            workspace=workspace_out(Membership(workspace, WorkspaceRole.OWNER)),
        )

    async def login(self, request: LoginRequest) -> TokenResponse:
        email = request.email.lower()
        op = "auth.login"
        with timed_stage(
            logger, op, "user_lookup", collection="users", email_domain=email_domain(email)
        ):
            user = await self._users.get_by_email(email)
        # user_found separates "unknown email" from "wrong password" in the server log only;
        # the client gets the same 401 either way.
        with timed_stage(logger, op, "password_verify", user_found=user is not None):
            valid = verify_password(request.password, user.password_hash if user else None)
            if user is None or not valid or not user.is_active:
                raise AppError(401, "invalid_credentials", "Incorrect email or password.")
        with timed_stage(logger, op, "token_create"):
            token, expires_in = create_access_token(user.id, self._settings)
        return TokenResponse(access_token=token, expires_in=expires_in)

    async def me(self, user: User) -> MeResponse:
        memberships = await self._workspaces.list_for_user(user.id)
        return MeResponse(user=user_out(user), workspaces=[workspace_out(m) for m in memberships])
