"""Direct-to-bucket uploads: the pieces that don't need MongoDB (tokens, checks, storage)."""

import base64
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from botocore.stub import Stubber

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    ExpiredTokenError,
    InvalidTokenError,
    UploadTicket,
    create_access_token,
    create_upload_token,
    decode_access_token,
    decode_upload_token,
)
from app.services.uploads import validate_head
from app.storage import create_storage
from app.storage.base import InvalidStorageKeyError, StoredFileMissingError
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage
from app.storage.unconfigured import UnconfiguredStorage
from tests.conftest import fixture_bytes


def _ticket() -> UploadTicket:
    return UploadTicket(
        user_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        storage_key=f"{uuid.uuid4().hex}.pdf",
        filename="Quarterly report.pdf",
        size_bytes=42 * 1024 * 1024,
    )


def test_upload_token_round_trips(settings: Settings) -> None:
    ticket = _ticket()

    assert decode_upload_token(create_upload_token(ticket, 900, settings), settings) == ticket


def test_upload_token_is_not_an_access_token_and_vice_versa(settings: Settings) -> None:
    upload_token = create_upload_token(_ticket(), 900, settings)
    access_token, _ = create_access_token(uuid.uuid4(), settings)

    with pytest.raises(InvalidTokenError):
        decode_access_token(upload_token, settings)
    with pytest.raises(InvalidTokenError):
        decode_upload_token(access_token, settings)


def test_expired_upload_token_is_reported_as_expired(settings: Settings) -> None:
    # The token outlives the URL by 300 s; a negative lifetime puts expiry in the past.
    token = create_upload_token(_ticket(), -301, settings)

    with pytest.raises(ExpiredTokenError):
        decode_upload_token(token, settings)


def test_tampered_upload_token_is_rejected(settings: Settings) -> None:
    header, payload, signature = create_upload_token(_ticket(), 900, settings).split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["size"] = 1
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()

    with pytest.raises(InvalidTokenError):
        decode_upload_token(f"{header}.{forged}.{signature}", settings)


@pytest.mark.parametrize(
    ("extension", "fixture"),
    [(".pdf", "two_pages.pdf"), (".docx", "sample.docx"), (".txt", "sample.txt")],
)
def test_head_of_a_matching_file_passes(extension: str, fixture: str) -> None:
    data = fixture_bytes(fixture)

    validate_head(extension, data[:8192], len(data))


@pytest.mark.parametrize(
    ("extension", "head"),
    [
        (".pdf", b"MZ\x90\x00 an executable"),
        (".docx", b"%PDF-1.7"),
        (".txt", b"text\x00with a NUL"),
        (".md", b"\xff\xfe not utf-8"),
    ],
)
def test_head_of_a_mismatched_file_is_rejected(extension: str, head: bytes) -> None:
    with pytest.raises(AppError) as exc_info:
        validate_head(extension, head, 10_000)

    assert exc_info.value.code == "content_mismatch"


def test_text_sample_may_end_inside_a_multibyte_character() -> None:
    data = "é".encode() * 10
    head = data[:5]  # cuts the third "é" in half

    validate_head(".txt", head, len(data))
    with pytest.raises(AppError):
        # The same bytes as a whole file are invalid UTF-8.
        validate_head(".txt", head, len(head))


async def test_local_storage_has_no_upload_url_but_reports_size_and_head(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    key = f"{uuid.uuid4().hex}.txt"

    assert await storage.presign_upload(key, "text/plain", 5, 900) is None
    assert await storage.size(key) is None
    with pytest.raises(StoredFileMissingError):
        await storage.read_head(key, 4)

    await storage.save(key, b"hello world")

    assert await storage.size(key) == 11
    assert await storage.read_head(key, 5) == b"hello"
    with pytest.raises(InvalidStorageKeyError):
        await storage.size("../escape.txt")


def _s3() -> S3Storage:
    return S3Storage(
        bucket="copilot-uploads",
        endpoint_url=None,
        region="ap-south-1",
        access_key_id="AKIAEXAMPLEEXAMPLE00",
        secret_access_key="example-secret-not-real",
    )


def _policy(fields: dict[str, str]) -> dict[str, Any]:
    policy: dict[str, Any] = json.loads(base64.b64decode(fields["policy"]))
    return policy


async def test_s3_upload_url_pins_key_type_and_exact_size() -> None:
    key = f"{uuid.uuid4().hex}.pdf"

    presigned = await _s3().presign_upload(key, "application/pdf", 50 * 1024 * 1024, 900)

    assert presigned is not None
    assert presigned.url == "https://copilot-uploads.s3.ap-south-1.amazonaws.com/"
    assert presigned.fields["x-amz-algorithm"] == "AWS4-HMAC-SHA256"
    assert presigned.fields["key"] == key
    assert presigned.fields["Content-Type"] == "application/pdf"
    conditions = _policy(presigned.fields)["conditions"]
    assert ["content-length-range", 50 * 1024 * 1024, 50 * 1024 * 1024] in conditions
    assert {"Content-Type": "application/pdf"} in conditions
    assert {"key": key} in conditions
    assert "example-secret-not-real" not in json.dumps(presigned.fields)


async def test_s3_upload_url_refuses_keys_the_service_did_not_generate() -> None:
    with pytest.raises(InvalidStorageKeyError):
        await _s3().presign_upload("../../other-tenant/file.pdf", "application/pdf", 10, 900)


async def test_s3_size_is_none_for_a_missing_object_and_head_is_a_range_read() -> None:
    storage = _s3()
    key = f"{uuid.uuid4().hex}.txt"
    with Stubber(storage._client) as stub:
        stub.add_client_error("head_object", service_error_code="404", http_status_code=404)
        stub.add_response(
            "head_object", {"ContentLength": 1234}, {"Bucket": "copilot-uploads", "Key": key}
        )
        stub.add_response(
            "get_object",
            {"Body": _Body(b"hello")},
            {"Bucket": "copilot-uploads", "Key": key, "Range": "bytes=0-4"},
        )

        assert await storage.size(key) is None
        assert await storage.size(key) == 1234
        assert await storage.read_head(key, 5) == b"hello"


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


async def test_vercel_deployments_without_s3_refuse_file_operations_only(
    settings: Settings,
) -> None:
    deployed = settings.model_copy(update={"vercel_env": "production"})

    storage = create_storage(deployed)

    assert isinstance(storage, UnconfiguredStorage)
    for operation in (
        storage.save(f"{uuid.uuid4().hex}.txt", b"x"),
        storage.presign_upload(f"{uuid.uuid4().hex}.txt", "text/plain", 1, 900),
    ):
        with pytest.raises(AppError) as exc_info:
            await operation
        assert (exc_info.value.status_code, exc_info.value.code) == (503, "storage_not_configured")


def test_local_storage_is_kept_outside_vercel_deployments(settings: Settings) -> None:
    # `vercel dev` on a laptop reports "development" and may use a local directory.
    for vercel_env in (None, "development"):
        local = settings.model_copy(update={"vercel_env": vercel_env})
        assert isinstance(create_storage(local), LocalStorage)
