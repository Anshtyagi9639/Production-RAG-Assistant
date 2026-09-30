import pytest

from app.core.errors import AppError
from app.services.uploads import sanitize_filename, validate_upload
from tests.conftest import fixture_bytes

MAX_BYTES = 1024 * 1024


@pytest.mark.parametrize(
    ("fixture", "content_type"),
    [
        ("two_pages.pdf", "application/pdf"),
        ("corrupted.pdf", "application/pdf"),  # right header; fails later in the worker
        (
            "sample.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("sample.txt", "text/plain"),
        ("sample.md", "text/markdown"),
    ],
)
def test_supported_files_are_accepted(fixture: str, content_type: str) -> None:
    upload = validate_upload(fixture, fixture_bytes(fixture), MAX_BYTES)

    assert upload.filename == fixture
    assert upload.content_type == content_type
    assert upload.data == fixture_bytes(fixture)


def _rejected(filename: str, data: bytes, max_bytes: int = MAX_BYTES) -> AppError:
    with pytest.raises(AppError) as exc_info:
        validate_upload(filename, data, max_bytes)
    return exc_info.value


def test_executable_renamed_to_pdf_is_rejected_by_magic_bytes() -> None:
    error = _rejected("invoice.pdf", fixture_bytes("disguised_exe.pdf"))

    assert (error.status_code, error.code) == (415, "content_mismatch")


def test_unsupported_extension_is_rejected() -> None:
    error = _rejected("setup.exe", b"MZ\x90\x00")

    assert (error.status_code, error.code) == (415, "unsupported_file_type")


def test_empty_file_is_rejected() -> None:
    error = _rejected("empty.txt", fixture_bytes("empty.txt"))

    assert (error.status_code, error.code) == (400, "empty_file")


def test_file_over_the_limit_is_rejected() -> None:
    error = _rejected("big.txt", b"a" * 11, max_bytes=10)

    assert (error.status_code, error.code) == (413, "file_too_large")


def test_zip_without_a_word_document_is_not_a_docx() -> None:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "not a document")

    error = _rejected("report.docx", buffer.getvalue())

    assert error.code == "content_mismatch"


@pytest.mark.parametrize("data", [b"text\x00with a nul byte", b"\xff\xfe\xfa not utf-8"])
def test_binary_content_in_text_files_is_rejected(data: bytes) -> None:
    assert _rejected("notes.txt", data).code == "content_mismatch"


def test_extension_check_is_case_insensitive() -> None:
    upload = validate_upload("REPORT.PDF", fixture_bytes("two_pages.pdf"), MAX_BYTES)

    assert upload.extension == ".pdf"
    assert upload.filename == "REPORT.PDF"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.txt", "passwd.txt"),
        ("..\\..\\windows\\system.ini.md", "system.ini.md"),
        ("/absolute/path/report.pdf", "report.pdf"),
        ("bad\x00name\x1f.txt", "badname.txt"),
        ("  spaced.md  ", "spaced.md"),
        (None, ""),
    ],
)
def test_filenames_are_reduced_to_a_safe_base_name(raw: str | None, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_long_filenames_are_truncated_keeping_the_extension() -> None:
    name = sanitize_filename("a" * 300 + ".pdf")

    assert len(name) == 255
    assert name.endswith(".pdf")
