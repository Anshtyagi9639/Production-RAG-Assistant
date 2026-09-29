"""Minimal valid rows for database tests."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityLog,
    AgentRun,
    Conversation,
    Document,
    DocumentChunk,
    Message,
    User,
    Workspace,
    WorkspaceMember,
)
from app.models.enums import MessageRole, WorkspaceRole


async def add_user(session: AsyncSession, email: str | None = None) -> User:
    user = User(
        email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="not-a-real-hash",
        full_name="Test User",
    )
    session.add(user)
    await session.flush()
    return user


async def add_workspace(session: AsyncSession, owner: User) -> Workspace:
    workspace = Workspace(name="Test Workspace")
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role=WorkspaceRole.OWNER)
    )
    await session.flush()
    return workspace


async def add_document(
    session: AsyncSession, workspace: Workspace, uploader: User | None, filename: str = "a.pdf"
) -> Document:
    document = Document(
        workspace_id=workspace.id,
        uploaded_by_id=uploader.id if uploader else None,
        filename=filename,
        storage_key=f"{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )
    session.add(document)
    await session.flush()
    return document


async def add_workspace_content(
    session: AsyncSession, workspace: Workspace, user: User
) -> dict[str, uuid.UUID]:
    """One row in every workspace-owned table, created by `user`. Returns their ids."""
    document = await add_document(session, workspace, user)
    chunk = DocumentChunk(
        document_id=document.id,
        workspace_id=workspace.id,
        chunk_index=0,
        page=1,
        text="Refunds are processed within 14 days.",
        token_count=8,
    )
    conversation = Conversation(workspace_id=workspace.id, user_id=user.id, title="Refunds")
    session.add_all([chunk, conversation])
    await session.flush()
    message = Message(
        conversation_id=conversation.id, role=MessageRole.USER, content="How long do refunds take?"
    )
    run = AgentRun(workspace_id=workspace.id, user_id=user.id, request="Summarize refund policy")
    activity = ActivityLog(
        workspace_id=workspace.id,
        user_id=user.id,
        action="document.uploaded",
        entity_type="document",
        entity_id=document.id,
    )
    session.add_all([message, run, activity])
    await session.flush()
    return {
        "document": document.id,
        "chunk": chunk.id,
        "conversation": conversation.id,
        "message": message.id,
        "agent_run": run.id,
        "activity": activity.id,
    }
