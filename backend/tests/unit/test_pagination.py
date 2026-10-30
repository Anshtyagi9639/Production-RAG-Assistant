import pytest
from pydantic import ValidationError

from app.core.errors import AppError
from app.core.pagination import Page, PageParams, sort_spec

ALLOWED = {"created_at": "created_at", "filename": "filename"}


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


def test_descending_sort_adds_an_id_tiebreaker() -> None:
    assert sort_spec("-created_at", ALLOWED) == [("created_at", -1), ("_id", -1)]


def test_ascending_sort() -> None:
    assert sort_spec("filename", ALLOWED) == [("filename", 1), ("_id", 1)]


def test_unknown_sort_field_is_rejected_with_the_allowed_fields() -> None:
    with pytest.raises(AppError) as exc_info:
        sort_spec("-password_hash", ALLOWED)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "invalid_sort"
    assert exc_info.value.details == {"allowed": ["created_at", "filename"]}
