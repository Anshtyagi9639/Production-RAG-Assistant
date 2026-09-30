import math
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.errors import AppError

MAX_PAGE_SIZE = 100

SortColumn = ColumnElement[Any] | InstrumentedAttribute[Any]


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page[ItemT](BaseModel):
    items: list[ItemT]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: Sequence[ItemT], total: int, params: PageParams) -> "Page[ItemT]":
        return cls(
            items=list(items),
            total=total,
            page=params.page,
            page_size=params.page_size,
            pages=math.ceil(total / params.page_size),
        )


def apply_sort(
    statement: Select[Any],
    sort: str,
    allowed: Mapping[str, SortColumn],
    tiebreaker: SortColumn,
) -> Select[Any]:
    """Order by a whitelisted field. `sort` is a field name, prefixed with `-` for descending.

    The tiebreaker (normally the primary key) keeps page boundaries stable when sort values tie.
    """
    descending = sort.startswith("-")
    field = sort.removeprefix("-")
    column = allowed.get(field)
    if column is None:
        raise AppError(
            400,
            "invalid_sort",
            f"Cannot sort by '{field}'.",
            details={"allowed": sorted(allowed)},
        )
    if descending:
        return statement.order_by(column.desc(), tiebreaker.desc())
    return statement.order_by(column.asc(), tiebreaker.asc())


def count_statement(statement: Select[Any]) -> Select[tuple[int]]:
    """COUNT(*) over the same filters, without the ordering (which a count doesn't need)."""
    return select(func.count()).select_from(statement.order_by(None).subquery())


async def paginate(
    session: AsyncSession, statement: Select[Any], params: PageParams
) -> tuple[list[Any], int]:
    """Return one page of scalar results and the total number of matching rows."""
    total = await session.scalar(count_statement(statement)) or 0
    result = await session.scalars(statement.limit(params.page_size).offset(params.offset))
    return list(result.all()), total
