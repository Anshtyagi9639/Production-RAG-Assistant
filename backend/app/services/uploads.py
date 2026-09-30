"""Upload validation: extension allow-list, size, emptiness, and magic bytes.

Content is checked against the claimed extension so a renamed executable is rejected before it
is stored. Files that pass but are malformed inside (e.g. a truncated PDF) are accepted here
and end as FAILED with a readable reason when the worker extracts them.
"""

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


def validate_upload(raw_filename: str | None, data: bytes, max_bytes: int) -> ValidatedUpload:
    filename = sanitize_filename(raw_filename)
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in CONTENT_TYPES:
        raise AppError(
            415,
            "unsupported_file_type",
            "Only PDF, DOCX, TXT and Markdown (.md) files are supported.",
        )
    if len(data) > max_bytes:
        raise AppError(
            413,
            "file_too_large",
            f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.",
        )
    if not data:
        raise AppError(400, "empty_file", "The file is empty.")
    if not _content_matches(extension, data):
        raise AppError(
            415,
            "content_mismatch",
            f"The file's content doesn't match its {extension} extension.",
        )
    return ValidatedUpload(filename, extension, CONTENT_TYPES[extension], data)
