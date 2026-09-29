from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkspaceMember
from app.models.enums import WorkspaceRole
from tests.integration.factories import add_document, add_user, add_workspace

pytestmark = pytest.mark.integration


async def _expect_violation(
    session: AsyncSession, constraint: str, action: Callable[[], Awaitable[object]]
) -> None:
    """Run `action` in a savepoint and assert Postgres rejects it with the named constraint."""
    with pytest.raises(IntegrityError) as exc_info:
        async with session.begin_nested():
            await action()
    assert constraint in str(exc_info.value.orig)


async def test_email_must_be_unique(db_session: AsyncSession) -> None:
    await add_user(db_session, "ana@example.com")

    await _expect_violation(
        db_session, "uq_users_email", lambda: add_user(db_session, "ana@example.com")
    )


async def test_email_must_be_stored_lowercase(db_session: AsyncSession) -> None:
    await _expect_violation(
        db_session, "ck_users_email_lowercase", lambda: add_user(db_session, "Ana@Example.com")
    )


async def test_user_can_join_a_workspace_only_once(db_session: AsyncSession) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)

    async def join_again() -> None:
        db_session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role=WorkspaceRole.MEMBER)
        )
        await db_session.flush()

    await _expect_violation(db_session, "uq_workspace_members_workspace_id_user_id", join_again)


async def test_membership_role_is_restricted(db_session: AsyncSession) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)
    other = await add_user(db_session)

    await _expect_violation(
        db_session,
        "ck_workspace_members_role",
        lambda: db_session.execute(
            text(
                "INSERT INTO workspace_members (id, workspace_id, user_id, role) "
                "VALUES (gen_random_uuid(), :workspace_id, :user_id, 'admin')"
            ),
            {"workspace_id": workspace.id, "user_id": other.id},
        ),
    )


async def test_document_status_is_restricted_and_defaults_to_uploaded(
    db_session: AsyncSession,
) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)

    status = await db_session.scalar(
        text(
            "INSERT INTO documents (id, workspace_id, filename, storage_key, content_type, "
            "size_bytes) VALUES (gen_random_uuid(), :workspace_id, 'a.txt', 'k1', 'text/plain', 5) "
            "RETURNING status"
        ),
        {"workspace_id": workspace.id},
    )
    assert status == "UPLOADED"

    await _expect_violation(
        db_session,
        "ck_documents_status",
        lambda: db_session.execute(
            text(
                "INSERT INTO documents (id, workspace_id, filename, storage_key, content_type, "
                "size_bytes, status) VALUES (gen_random_uuid(), :workspace_id, 'b.txt', 'k2', "
                "'text/plain', 5, 'DONE')"
            ),
            {"workspace_id": workspace.id},
        ),
    )


async def test_empty_documents_are_rejected(db_session: AsyncSession) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)

    async def add_empty() -> None:
        document = await add_document(db_session, workspace, owner)
        document.size_bytes = 0
        await db_session.flush()

    await _expect_violation(db_session, "ck_documents_size_bytes_positive", add_empty)


async def test_chunk_index_is_unique_per_document(db_session: AsyncSession) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)
    document = await add_document(db_session, workspace, owner)
    insert = text(
        "INSERT INTO document_chunks (id, document_id, workspace_id, chunk_index, text, "
        "token_count) VALUES (gen_random_uuid(), :document_id, :workspace_id, 0, 'x', 1)"
    )
    params = {"document_id": document.id, "workspace_id": workspace.id}
    await db_session.execute(insert, params)

    await _expect_violation(
        db_session,
        "uq_document_chunks_document_id_chunk_index",
        lambda: db_session.execute(insert, params),
    )


async def test_jsonb_and_counter_columns_have_server_defaults(db_session: AsyncSession) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)

    row = (
        await db_session.execute(
            text(
                "INSERT INTO agent_runs (id, workspace_id, request) "
                "VALUES (gen_random_uuid(), :workspace_id, 'q') "
                "RETURNING status, trace, sources, is_partial, prompt_tokens, completion_tokens"
            ),
            {"workspace_id": workspace.id},
        )
    ).one()

    assert tuple(row) == ("QUEUED", [], [], False, 0, 0)
