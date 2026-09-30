import uuid
from pathlib import Path

import pytest

from app.storage.base import InvalidStorageKeyError, StoredFileMissingError
from app.storage.local import LocalStorage


def _key(extension: str = ".pdf") -> str:
    return f"{uuid.uuid4().hex}{extension}"


async def test_save_read_and_delete(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "uploads")
    key = _key()

    await storage.save(key, b"%PDF-1.4 content")

    assert (tmp_path / "uploads" / key).read_bytes() == b"%PDF-1.4 content"
    assert await storage.read(key) == b"%PDF-1.4 content"
    await storage.delete(key)
    assert not (tmp_path / "uploads" / key).exists()


async def test_reading_a_missing_file_raises_a_user_facing_error(tmp_path: Path) -> None:
    with pytest.raises(StoredFileMissingError, match="could not be found"):
        await LocalStorage(tmp_path).read(_key())


async def test_deleting_a_missing_file_is_a_no_op(tmp_path: Path) -> None:
    await LocalStorage(tmp_path).delete(_key())


@pytest.mark.parametrize(
    "key",
    [
        "../outside.pdf",
        "..\\outside.pdf",
        "/etc/passwd",
        "report.pdf",
        f"{uuid.uuid4().hex}.exe",
        f"{uuid.uuid4().hex}.pdf/../../x.pdf",
    ],
)
async def test_keys_that_are_not_generated_names_are_refused(tmp_path: Path, key: str) -> None:
    storage = LocalStorage(tmp_path / "uploads")

    with pytest.raises(InvalidStorageKeyError):
        await storage.save(key, b"data")
    assert not any(tmp_path.rglob("*"))
