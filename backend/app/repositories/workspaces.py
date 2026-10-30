import uuid
from dataclasses import dataclass

from app.db.mongo import Database, Session
from app.models import Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole


@dataclass(frozen=True)
class Membership:
    workspace: Workspace
    role: WorkspaceRole


class WorkspaceRepository:
    def __init__(self, db: Database) -> None:
        self._workspaces = db["workspaces"]
        self._members = db["workspace_members"]

    async def insert(self, workspace: Workspace, session: Session | None = None) -> None:
        await self._workspaces.insert_one(workspace.to_document(), session=session)

    async def insert_member(self, member: WorkspaceMember, session: Session | None = None) -> None:
        await self._members.insert_one(member.to_document(), session=session)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Membership]:
        roles = {
            document["workspace_id"]: WorkspaceRole(document["role"])
            async for document in self._members.find({"user_id": user_id})
        }
        if not roles:
            return []
        cursor = self._workspaces.find({"_id": {"$in": list(roles)}}).sort(
            [("created_at", 1), ("_id", 1)]
        )
        return [
            Membership(Workspace.from_document(document), roles[document["_id"]])
            async for document in cursor
        ]

    async def get_membership(
        self, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Membership | None:
        member = await self._members.find_one({"workspace_id": workspace_id, "user_id": user_id})
        if member is None:
            return None
        workspace = await self._workspaces.find_one({"_id": workspace_id})
        if workspace is None:
            return None
        return Membership(Workspace.from_document(workspace), WorkspaceRole(member["role"]))

    async def is_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, session: Session | None = None
    ) -> bool:
        member = await self._members.find_one(
            {"workspace_id": workspace_id, "user_id": user_id}, {"_id": 1}, session=session
        )
        return member is not None
