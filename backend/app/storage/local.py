import asyncio
from pathlib import Path

from app.storage.base import StoredFileMissingError, validate_key


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
