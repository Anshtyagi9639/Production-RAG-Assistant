import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole


@dataclass(frozen=True)
class Membership:
    workspace: Workspace
    role: WorkspaceRole


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, workspace: Workspace) -> None:
        self._session.add(workspace)

    def add_member(self, member: WorkspaceMember) -> None:
        self._session.add(member)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Membership]:
        rows = await self._session.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at, Workspace.id)
        )
        return [Membership(workspace, role) for workspace, role in rows.tuples()]

    async def get_membership(
        self, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Membership | None:
        row = (
            await self._session.execute(
                select(Workspace, WorkspaceMember.role)
                .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
                .where(Workspace.id == workspace_id, WorkspaceMember.user_id == user_id)
            )
        ).first()
        return Membership(row[0], row[1]) if row else None

    async def get_member_user(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceMember | None:
        member: WorkspaceMember | None = await self._session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id
            )
        )
        return member
