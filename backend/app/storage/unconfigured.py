from app.core.errors import AppError
from app.storage.base import PresignedUpload

STORAGE_NOT_CONFIGURED = AppError(
    503,
    "storage_not_configured",
    "File storage isn't configured on this deployment, so documents can't be uploaded yet.",
)


class UnconfiguredStorage:
    """Stands in for local storage on a deployment whose disk can't keep files: every file
    operation answers 503, and nothing that doesn't touch files is affected."""

    async def save(self, key: str, data: bytes) -> None:
        raise STORAGE_NOT_CONFIGURED

    async def read(self, key: str) -> bytes:
        raise STORAGE_NOT_CONFIGURED

    async def delete(self, key: str) -> None:
        raise STORAGE_NOT_CONFIGURED

    async def presign_upload(
        self, key: str, content_type: str, size_bytes: int, expires_seconds: int
    ) -> PresignedUpload | None:
        raise STORAGE_NOT_CONFIGURED

    async def size(self, key: str) -> int | None:
        raise STORAGE_NOT_CONFIGURED

    async def read_head(self, key: str, length: int) -> bytes:
        raise STORAGE_NOT_CONFIGURED
