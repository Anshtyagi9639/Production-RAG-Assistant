import asyncio
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.storage.base import StoredFileMissingError, validate_key


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
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
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
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                raise StoredFileMissingError from exc
            raise
        body: bytes = await asyncio.to_thread(response["Body"].read)
        return body

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=validate_key(key)
        )
