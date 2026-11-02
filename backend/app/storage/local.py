import asyncio
from pathlib import Path

from app.storage.base import PresignedUpload, StoredFileMissingError, validate_key


class LocalStorage:
    """Files in a directory. The API and worker must share it (a Docker volume in compose)."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / validate_key(key)).resolve()
        if path.parent != self._root:
            raise ValueError("Storage path escapes the storage root")
        return path

    async def save(self, key: str, data: bytes) -> None:
        path = self._path(key)

        def write() -> None:
            self._root.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(write)

    async def read(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise StoredFileMissingError from exc

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, missing_ok=True)

    async def presign_upload(
        self, key: str, content_type: str, size_bytes: int, expires_seconds: int
    ) -> PresignedUpload | None:
        # A directory has no upload URL: files reach it through the API.
        return None

    async def size(self, key: str) -> int | None:
        path = self._path(key)
        try:
            return (await asyncio.to_thread(path.stat)).st_size
        except FileNotFoundError:
            return None

    async def read_head(self, key: str, length: int) -> bytes:
        path = self._path(key)

        def read() -> bytes:
            with path.open("rb") as file:
                return file.read(length)

        try:
            return await asyncio.to_thread(read)
        except FileNotFoundError as exc:
            raise StoredFileMissingError from exc
