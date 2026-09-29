from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import Select, select
from sqlalchemy.dialects import postgresql

from app.core.errors import AppError
from app.core.pagination import Page, PageParams, apply_sort, count_statement
from app.models import Document

ALLOWED_SORTS = {"created_at": Document.created_at, "filename": Document.filename}


def _sql(statement: Select[Any]) -> str:
    return " ".join(str(statement.compile(dialect=postgresql.dialect())).split())


@pytest.mark.parametrize(("page", "page_size", "offset"), [(1, 20, 0), (2, 20, 20), (3, 7, 14)])
def test_offset_is_derived_from_page_and_size(page: int, page_size: int, offset: int) -> None:
    assert PageParams(page=page, page_size=page_size).offset == offset


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
def test_out_of_range_page_params_are_rejected(params: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        PageParams(**params)


@pytest.mark.parametrize(("total", "pages"), [(0, 0), (1, 1), (20, 1), (21, 2)])
def test_page_count_rounds_up(total: int, pages: int) -> None:
    page = Page[str].build(["a"], total, PageParams(page=1, page_size=20))

    assert page.pages == pages
    assert page.total == total
    assert page.items == ["a"]


def test_descending_sort_adds_primary_key_tiebreaker() -> None:
    statement = apply_sort(select(Document), "-created_at", ALLOWED_SORTS, Document.id)

    assert _sql(statement).endswith("ORDER BY documents.created_at DESC, documents.id DESC")


def test_ascending_sort() -> None:
    statement = apply_sort(select(Document), "filename", ALLOWED_SORTS, Document.id)

    assert _sql(statement).endswith("ORDER BY documents.filename ASC, documents.id ASC")


def test_unknown_sort_field_is_rejected_with_the_allowed_fields() -> None:
    with pytest.raises(AppError) as exc_info:
        apply_sort(select(Document), "-password_hash", ALLOWED_SORTS, Document.id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "invalid_sort"
    assert exc_info.value.details == {"allowed": ["created_at", "filename"]}


def test_count_statement_keeps_filters_and_drops_ordering() -> None:
    statement = select(Document).where(Document.status == "COMPLETED").order_by(Document.created_at)

    sql = _sql(count_statement(statement))

    assert sql.startswith("SELECT count(*) AS count_1 FROM (SELECT")
    assert "WHERE documents.status = %(status_1)s" in sql
    assert "ORDER BY" not in sql
