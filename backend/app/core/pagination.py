import math
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, Field

from app.core.errors import AppError

MAX_PAGE_SIZE = 100
ASCENDING, DESCENDING = 1, -1


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


def sort_spec(sort: str, allowed: Mapping[str, str]) -> list[tuple[str, int]]:
    """MongoDB sort for a whitelisted field. `sort` is a field name, `-`-prefixed for descending.

    `_id` is added as a tiebreaker so page boundaries stay stable when sort values tie.
    """
    direction = DESCENDING if sort.startswith("-") else ASCENDING
    name = sort.removeprefix("-")
    field = allowed.get(name)
    if field is None:
        raise AppError(
            400, "invalid_sort", f"Cannot sort by '{name}'.", details={"allowed": sorted(allowed)}
        )
    return [(field, direction), ("_id", direction)]
