"""Direct-to-bucket uploads through the API, on MongoDB Atlas.

The bucket is a local directory whose "upload URL" is fake: tests put the file in place the
way the browser's POST to S3 would, then call /documents/upload/complete.
"""

import uuid

import pytest

from app.db.mongo import Mongo
from app.storage.base import PresignedUpload
from app.storage.local import LocalStorage
from tests.conftest import fixture_bytes
from tests.integration.api_helpers import Account, register
from tests.integration.conftest import Api

pytestmark = pytest.mark.integration


class PresigningStorage(LocalStorage):
    async def presign_upload(
        self, key: str, content_type: str, size_bytes: int, expires_seconds: int
    ) -> PresignedUpload | None:
        return PresignedUpload(url="https://bucket.test/", fields={"key": key})


@pytest.fixture
def bucket(api: Api) -> PresigningStorage:
    storage = PresigningStorage(api.storage_root)
    api.app.state.storage = storage
    return storage


async def _start(api: Api, account: Account, filename: str, size: int) -> dict[str, object]:
    response = await api.client.post(
        "/api/documents/upload/direct",
        json={"filename": filename, "size_bytes": size},
        headers=account.headers(),
    )
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


async def _complete(api: Api, account: Account, token: object) -> tuple[int, dict[str, object]]:
    response = await api.client.post(
        "/api/documents/upload/complete",
        json={"upload_token": token},
        headers=account.headers(),
    )
    return response.status_code, response.json()


async def test_direct_upload_records_queues_and_is_idempotent(
    api: Api, mongo: Mongo, bucket: PresigningStorage
) -> None:
    account = await register(api.client, "direct@example.com", "Dee Rect")
    data = fixture_bytes("two_pages.pdf")

    started = await _start(api, account, "two_pages.pdf", len(data))
    key = started["fields"]["key"]  # type: ignore[index]
    await bucket.save(str(key), data)
    status, body = await _complete(api, account, started["upload_token"])
    again_status, again = await _complete(api, account, started["upload_token"])

    assert status == 202
    assert body["status"] == "UPLOADED"
    assert (body["filename"], body["size_bytes"]) == ("two_pages.pdf", len(data))
    assert body["uploaded_by_name"] == "Dee Rect"
    assert (again_status, again["id"]) == (202, body["id"])
    document = await mongo.db["documents"].find_one({"_id": uuid.UUID(str(body["id"]))})
    assert document is not None
    assert document["storage_key"] == key
    assert document["workspace_id"] == account.workspace_id
    [job] = api.queue.jobs
    assert job.document_id == document["_id"]
    assert await mongo.db["activity_logs"].count_documents({"action": "document.uploaded"}) == 1


async def test_completing_before_the_file_arrived_is_409(
    api: Api, mongo: Mongo, bucket: PresigningStorage
) -> None:
    account = await register(api.client, "early@example.com")

    started = await _start(api, account, "notes.txt", 10)
    status, body = await _complete(api, account, started["upload_token"])

    assert (status, body["error"]["code"]) == (409, "upload_incomplete")  # type: ignore[index]
    assert await mongo.db["documents"].count_documents({}) == 0


async def test_disguised_file_is_deleted_from_the_bucket_and_never_recorded(
    api: Api, mongo: Mongo, bucket: PresigningStorage
) -> None:
    account = await register(api.client, "disguise@example.com")
    data = fixture_bytes("disguised_exe.pdf")

    started = await _start(api, account, "invoice.pdf", len(data))
    key = str(started["fields"]["key"])  # type: ignore[index]
    await bucket.save(key, data)
    status, body = await _complete(api, account, started["upload_token"])

    assert (status, body["error"]["code"]) == (415, "content_mismatch")  # type: ignore[index]
    assert await bucket.size(key) is None
    assert await mongo.db["documents"].count_documents({}) == 0
    assert api.queue.jobs == []


async def test_a_ticket_is_only_valid_for_its_own_user_and_workspace(
    api: Api, mongo: Mongo, bucket: PresigningStorage
) -> None:
    owner = await register(api.client, "owner@example.com")
    other = await register(api.client, "other@example.com")
    data = b"hello"
    started = await _start(api, owner, "hello.txt", len(data))
    await bucket.save(str(started["fields"]["key"]), data)  # type: ignore[index]

    status, body = await _complete(api, other, started["upload_token"])
    forged_status, forged = await _complete(api, owner, "not-a-token")

    assert (status, body["error"]["code"]) == (400, "invalid_upload")  # type: ignore[index]
    assert (forged_status, forged["error"]["code"]) == (400, "invalid_upload")  # type: ignore[index]
    assert await mongo.db["documents"].count_documents({}) == 0


@pytest.mark.parametrize(
    ("filename", "size", "status", "code"),
    [
        ("big.pdf", 10**12, 413, "file_too_large"),
        ("empty.txt", 0, 400, "empty_file"),
        ("setup.exe", 100, 415, "unsupported_file_type"),
    ],
)
async def test_bad_requests_get_no_upload_url(
    api: Api, bucket: PresigningStorage, filename: str, size: int, status: int, code: str
) -> None:
    account = await register(api.client, f"bad-{code}@example.com")

    response = await api.client.post(
        "/api/documents/upload/direct",
        json={"filename": filename, "size_bytes": size},
        headers=account.headers(),
    )

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


async def test_local_storage_answers_409_so_the_client_falls_back(api: Api) -> None:
    account = await register(api.client, "local@example.com")

    response = await api.client.post(
        "/api/documents/upload/direct",
        json={"filename": "a.txt", "size_bytes": 5},
        headers=account.headers(),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "direct_upload_unavailable"
