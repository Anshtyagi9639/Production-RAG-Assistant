"""Upload validation: extension allow-list, size, emptiness, and magic bytes.

Content is checked against the claimed extension so a renamed executable is rejected before it
is stored (or, for a file uploaded straight to the bucket, deleted before it's recorded). Files
that pass but are malformed inside (e.g. a truncated PDF) are accepted here and end as FAILED
with a readable reason when the worker extracts them.
"""

import codecs
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.core.errors import AppError

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}
MAX_FILENAME_LENGTH = 255
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_ZIP_SIGNATURE = b"PK\x03\x04"
# Bytes of a directly uploaded file read back to check it matches its extension.
HEAD_SAMPLE_BYTES = 8 * 1024


@dataclass(frozen=True)
class ValidatedName:
    filename: str
    extension: str
    content_type: str


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    extension: str
    content_type: str
    data: bytes


def sanitize_filename(raw: str | None) -> str:
    """Keep only the base name, without directories or control characters."""
    name = PurePosixPath((raw or "").replace("\\", "/")).name
    name = _CONTROL_CHARS.sub("", unicodedata.normalize("NFC", name)).strip()
    if len(name) > MAX_FILENAME_LENGTH:
        path = PurePosixPath(name)
        name = path.stem[: MAX_FILENAME_LENGTH - len(path.suffix)] + path.suffix
    return name


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def _is_utf8_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _content_matches(extension: str, data: bytes) -> bool:
    if extension == ".pdf":
        return data.startswith(b"%PDF-")
    if extension == ".docx":
        return _is_docx(data)
    return _is_utf8_text(data)


def _head_matches(extension: str, head: bytes, complete: bool) -> bool:
    """The same check on only the first bytes of a file uploaded straight to the bucket.

    A DOCX is recognised by its ZIP signature here; its structure is checked when the worker
    extracts it. Text may end in the middle of a UTF-8 sequence when the sample is cut short.
    """
    if extension == ".pdf":
        return head.startswith(b"%PDF-")
    if extension == ".docx":
        return head.startswith(_ZIP_SIGNATURE)
    if b"\x00" in head:
        return False
    try:
        codecs.getincrementaldecoder("utf-8")().decode(head, final=complete)
    except UnicodeDecodeError:
        return False
    return True


def validate_filename(raw_filename: str | None) -> ValidatedName:
    filename = sanitize_filename(raw_filename)
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in CONTENT_TYPES:
        raise AppError(
            415,
            "unsupported_file_type",
            "Only PDF, DOCX, TXT and Markdown (.md) files are supported.",
        )
    return ValidatedName(filename, extension, CONTENT_TYPES[extension])


def validate_size(size: int, max_bytes: int) -> None:
    if size > max_bytes:
        raise AppError(
            413,
            "file_too_large",
            f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.",
        )
    if size <= 0:
        raise AppError(400, "empty_file", "The file is empty.")


def _content_mismatch(extension: str) -> AppError:
    return AppError(
        415,
        "content_mismatch",
        f"The file's content doesn't match its {extension} extension.",
    )


def validate_upload(raw_filename: str | None, data: bytes, max_bytes: int) -> ValidatedUpload:
    name = validate_filename(raw_filename)
    validate_size(len(data), max_bytes)
    if not _content_matches(name.extension, data):
        raise _content_mismatch(name.extension)
    return ValidatedUpload(name.filename, name.extension, name.content_type, data)


def validate_head(extension: str, head: bytes, size: int) -> None:
    """Check a directly uploaded file from its first bytes (`head`) and its stored `size`."""
    if not _head_matches(extension, head, complete=len(head) >= size):
        raise _content_mismatch(extension)
