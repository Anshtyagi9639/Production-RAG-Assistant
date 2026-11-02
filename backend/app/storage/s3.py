import asyncio
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.storage.base import PresignedUpload, StoredFileMissingError, validate_key

_MISSING_CODES = {"NoSuchKey", "NotFound", "404"}


def _is_missing(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") in _MISSING_CODES


class S3Storage:
    """Files in an S3-compatible bucket (e.g. Cloudflare R2), so API and worker stay stateless."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None,
        region: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        self._bucket = bucket
        # SigV4 everywhere (boto3 would sign us-east-1 upload forms with the legacy SigV2). On
        # AWS, virtual-hosted addressing gives the bucket's regional URL: the global one can
        # answer a browser's upload with a redirect, which the upload can't follow.
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"} if endpoint_url is None else None,
        )
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=config,
        )

    async def save(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(
            self._client.put_object, Bucket=self._bucket, Key=validate_key(key), Body=data
        )

    async def read(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=validate_key(key)
            )
        except ClientError as exc:
            if _is_missing(exc):
                raise StoredFileMissingError from exc
            raise
        body: bytes = await asyncio.to_thread(response["Body"].read)
        return body

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=validate_key(key)
        )

    async def presign_upload(
        self, key: str, content_type: str, size_bytes: int, expires_seconds: int
    ) -> PresignedUpload | None:
        # Signed locally (no request to the bucket). The bucket itself refuses a body of any
        # other size, a different Content-Type, or a different key, and anything after expiry.
        post: dict[str, Any] = await asyncio.to_thread(
            self._client.generate_presigned_post,
            Bucket=self._bucket,
            Key=validate_key(key),
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", size_bytes, size_bytes],
            ],
            ExpiresIn=expires_seconds,
        )
        return PresignedUpload(url=post["url"], fields=dict(post["fields"]))

    async def size(self, key: str) -> int | None:
        try:
            response = await asyncio.to_thread(
                self._client.head_object, Bucket=self._bucket, Key=validate_key(key)
            )
        except ClientError as exc:
            if _is_missing(exc):
                return None
            raise
        length: int = response["ContentLength"]
        return length

    async def read_head(self, key: str, length: int) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self._bucket,
                Key=validate_key(key),
                Range=f"bytes=0-{length - 1}",
            )
        except ClientError as exc:
            if _is_missing(exc):
                raise StoredFileMissingError from exc
            raise
        body: bytes = await asyncio.to_thread(response["Body"].read)
        return body
