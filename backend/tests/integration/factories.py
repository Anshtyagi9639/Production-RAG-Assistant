"""Minimal valid records for database tests."""

import uuid

from app.core.security import hash_password
from app.db.mongo import Mongo
from app.models import Document, User, Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole


async def add_user(mongo: Mongo, email: str | None = None) -> User:
    user = User(
        email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("correct horse battery"),
        full_name="Test User",
    )
    await mongo.db["users"].insert_one(user.to_document())
    return user


async def add_workspace(mongo: Mongo, owner: User) -> Workspace:
    workspace = Workspace(name="Test Workspace")
    await mongo.db["workspaces"].insert_one(workspace.to_document())
    member = WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role=WorkspaceRole.OWNER)
    await mongo.db["workspace_members"].insert_one(member.to_document())
    return workspace


async def add_document(
    mongo: Mongo, workspace: Workspace, uploader: User | None, filename: str = "a.pdf"
) -> Document:
    document = Document(
        workspace_id=workspace.id,
        uploaded_by_id=uploader.id if uploader else None,
        filename=filename,
        storage_key=f"{uuid.uuid4().hex}.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )
    await mongo.db["documents"].insert_one(document.to_document())
    return document
