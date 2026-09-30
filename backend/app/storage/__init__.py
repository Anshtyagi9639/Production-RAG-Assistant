from pathlib import Path

from app.core.config import Settings
from app.storage.base import Storage
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


def create_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "s3":
        if not (settings.s3_bucket and settings.s3_access_key_id and settings.s3_secret_access_key):
            raise ValueError("S3 storage settings are incomplete")
        return S3Storage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id.get_secret_value(),
            secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        )
    return LocalStorage(Path(settings.storage_local_path))
