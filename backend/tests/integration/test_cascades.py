"""ON DELETE behaviour, exercised with SQL DELETEs so Postgres (not the ORM) does the work."""

import uuid

import pytest
from sqlalchemy import delete, func, select
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
from app.models.enums import WorkspaceRole
from tests.integration.factories import add_user, add_workspace, add_workspace_content

pytestmark = pytest.mark.integration

MODELS = {
    "document": Document,
    "chunk": DocumentChunk,
    "conversation": Conversation,
    "message": Message,
    "agent_run": AgentRun,
    "activity": ActivityLog,
}


async def _exists(session: AsyncSession, model: type, row_id: uuid.UUID) -> bool:
    count = await session.scalar(select(func.count()).select_from(model).where(model.id == row_id))
    return count == 1


async def test_deleting_a_workspace_deletes_everything_it_owns(db_session: AsyncSession) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)
    ids = await add_workspace_content(db_session, workspace, owner)
    other_workspace = await add_workspace(db_session, owner)
    other_ids = await add_workspace_content(db_session, other_workspace, owner)

    await db_session.execute(delete(Workspace).where(Workspace.id == workspace.id))
    db_session.expire_all()

    for name, model in MODELS.items():
        assert not await _exists(db_session, model, ids[name]), name
        assert await _exists(db_session, model, other_ids[name]), f"other workspace {name}"
    memberships = await db_session.scalar(
        select(func.count())
        .select_from(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace.id)
    )
    assert memberships == 0
    assert await _exists(db_session, User, owner.id)


async def test_deleting_a_user_removes_private_data_and_keeps_workspace_records(
    db_session: AsyncSession,
) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)
    member = await add_user(db_session)
    db_session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=member.id, role=WorkspaceRole.MEMBER)
    )
    ids = await add_workspace_content(db_session, workspace, member)

    await db_session.execute(delete(User).where(User.id == member.id))
    db_session.expire_all()

    # Private to the user: removed.
    assert not await _exists(db_session, Conversation, ids["conversation"])
    assert not await _exists(db_session, Message, ids["message"])
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(WorkspaceMember.user_id == member.id)
        )
        == 0
    )
    # Workspace records: kept, with the user reference cleared.
    document = await db_session.get_one(Document, ids["document"])
    run = await db_session.get_one(AgentRun, ids["agent_run"])
    activity = await db_session.get_one(ActivityLog, ids["activity"])
    assert document.uploaded_by_id is None
    assert run.user_id is None
    assert activity.user_id is None
    assert await _exists(db_session, DocumentChunk, ids["chunk"])
    assert await _exists(db_session, Workspace, workspace.id)


async def test_deleting_a_document_deletes_its_chunks_only(db_session: AsyncSession) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)
    ids = await add_workspace_content(db_session, workspace, owner)

    await db_session.execute(delete(Document).where(Document.id == ids["document"]))
    db_session.expire_all()

    assert not await _exists(db_session, DocumentChunk, ids["chunk"])
    assert await _exists(db_session, ActivityLog, ids["activity"])
    assert await _exists(db_session, Conversation, ids["conversation"])
