from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, apply_sort, paginate
from app.models import Document
from app.models.enums import DocumentStatus
from tests.integration.factories import add_document, add_user, add_workspace

pytestmark = pytest.mark.integration

SORTS = {"created_at": Document.created_at, "filename": Document.filename}


async def test_paginate_returns_the_requested_page_of_filtered_sorted_rows(
    db_session: AsyncSession,
) -> None:
    owner = await add_user(db_session)
    workspace = await add_workspace(db_session, owner)
    other_workspace = await add_workspace(db_session, owner)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for day in range(5):
        document = await add_document(db_session, workspace, owner, filename=f"doc-{day}.pdf")
        document.created_at = start + timedelta(days=day)
        document.status = DocumentStatus.COMPLETED if day % 2 == 0 else DocumentStatus.FAILED
    await add_document(db_session, other_workspace, owner, filename="other.pdf")
    await db_session.flush()

    in_workspace = select(Document).where(Document.workspace_id == workspace.id)
    newest_first = apply_sort(in_workspace, "-created_at", SORTS, Document.id)

    page_two, total = await paginate(db_session, newest_first, PageParams(page=2, page_size=2))
    assert total == 5
    assert [document.filename for document in page_two] == ["doc-2.pdf", "doc-1.pdf"]

    completed = apply_sort(
        in_workspace.where(Document.status == DocumentStatus.COMPLETED),
        "filename",
        SORTS,
        Document.id,
    )
    items, total = await paginate(db_session, completed, PageParams(page=1, page_size=10))
    assert total == 3
    assert [document.filename for document in items] == ["doc-0.pdf", "doc-2.pdf", "doc-4.pdf"]
