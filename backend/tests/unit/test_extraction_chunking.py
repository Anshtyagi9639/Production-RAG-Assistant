import uuid

import pytest

from app.rag.chunking import (
    CHUNK_SIZE_TOKENS,
    chunk_id,
    chunk_pages,
    clean_text,
)
from app.rag.extraction import ExtractionError, Page, extract
from tests.conftest import fixture_bytes


def test_pdf_pages_keep_their_numbers() -> None:
    document = extract(fixture_bytes("two_pages.pdf"), ".pdf")

    assert document.page_count == 2
    assert [page.number for page in document.pages] == [1, 2]
    assert "30 days of purchase" in document.pages[0].text
    assert "retained for 90 days" in document.pages[1].text


def test_docx_paragraphs_and_tables_are_extracted() -> None:
    document = extract(fixture_bytes("sample.docx"), ".docx")

    assert document.page_count is None
    text = document.pages[0].text
    assert "Security training must be completed" in text
    assert "Payroll | Finance team" in text


@pytest.mark.parametrize(
    ("fixture", "phrase"), [("sample.txt", "on-call"), ("sample.md", "40 EUR")]
)
def test_text_formats_are_read_as_utf8(fixture: str, phrase: str) -> None:
    document = extract(fixture_bytes(fixture), fixture[fixture.index(".") :])

    assert phrase in document.pages[0].text
    assert document.pages[0].number is None


@pytest.mark.parametrize(
    ("fixture", "extension", "reason"),
    [
        ("corrupted.pdf", ".pdf", "corrupted or not a valid PDF"),
        ("encrypted.pdf", ".pdf", "password-protected"),
        ("two_pages.pdf", ".docx", "not a valid Word document"),
    ],
)
def test_malformed_files_fail_with_a_readable_reason(
    fixture: str, extension: str, reason: str
) -> None:
    with pytest.raises(ExtractionError, match=reason):
        extract(fixture_bytes(fixture), extension)


def test_pdf_without_text_fails_at_chunking_with_a_readable_reason() -> None:
    document = extract(fixture_bytes("no_text.pdf"), ".pdf")

    with pytest.raises(ExtractionError, match="No extractable text"):
        chunk_pages(document.pages, uuid.uuid4())


def test_cleaning_normalizes_whitespace_and_drops_nul_bytes() -> None:
    raw = "  Title\t\t here \r\n\r\n\r\n\r\nBody\N{NO-BREAK SPACE}\N{NO-BREAK SPACE}text\x00 \n"

    assert clean_text(raw) == "Title here\n\nBody text"


def test_empty_pages_are_dropped_and_page_numbers_kept() -> None:
    pages = [Page(1, "First page text."), Page(2, "   \n\t "), Page(3, "Third page text.")]

    chunks = chunk_pages(pages, uuid.uuid4())

    assert [(chunk.index, chunk.page) for chunk in chunks] == [(0, 1), (1, 3)]


def test_long_text_is_split_into_overlapping_chunks_within_the_token_limit() -> None:
    sentences = [f"Sentence number {n} describes policy clause {n} in detail." for n in range(600)]
    document_id = uuid.uuid4()

    chunks = chunk_pages([Page(None, " ".join(sentences))], document_id)

    assert len(chunks) > 3
    assert all(0 < chunk.token_count <= CHUNK_SIZE_TOKENS for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    # Consecutive chunks share text (the ~120 token overlap).
    tail = chunks[0].text.split(".")[-2]
    assert tail.strip() in chunks[1].text


def test_chunk_ids_are_deterministic_per_document_and_index() -> None:
    document_id = uuid.uuid4()
    first = chunk_pages([Page(1, "Same text.")], document_id)
    second = chunk_pages([Page(1, "Same text.")], document_id)

    assert first[0].id == second[0].id == chunk_id(document_id, 0)
    assert chunk_id(document_id, 1) != chunk_id(document_id, 0)
    assert chunk_id(uuid.uuid4(), 0) != chunk_id(document_id, 0)
