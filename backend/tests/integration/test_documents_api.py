import uuid

import pytest

from app.db.mongo import Mongo
from app.models.enums import DocumentStatus
from app.rag.indexing import COLLECTION
from tests.conftest import fixture_bytes
from tests.fakes import RecordingJobQueue
from tests.integration.api_helpers import register, run_queued_jobs, upload
from tests.integration.conftest import Api

pytestmark = pytest.mark.integration


async def test_upload_stores_file_records_uploaded_and_queues_a_job(api: Api, mongo: Mongo) -> None:
    account = await register(api.client, "up@example.com", "Una Park")

    body = await upload(api, account, "two_pages.pdf", fixture_bytes("two_pages.pdf"))

    assert body["status"] == "UPLOADED"
    assert body["filename"] == "two_pages.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["uploaded_by_name"] == "Una Park"
    document = await mongo.db["documents"].find_one({"_id": uuid.UUID(str(body["id"]))})
    assert document is not None
    assert document["workspace_id"] == account.workspace_id
    assert (api.storage_root / document["storage_key"]).read_bytes() == fixture_bytes(
        "two_pages.pdf"
    )
    assert document["storage_key"] != "two_pages.pdf"
    [job] = api.queue.jobs
    assert (job.document_id, job.workspace_id) == (document["_id"], account.workspace_id)
    activity = await mongo.db["activity_logs"].find_one({"action": "document.uploaded"})
    assert activity is not None
    assert activity["details"] == {"filename": "two_pages.pdf"}


@pytest.mark.parametrize(
    ("filename", "fixture", "status", "code"),
    [
        ("empty.txt", "empty.txt", 400, "empty_file"),
        ("invoice.pdf", "disguised_exe.pdf", 415, "content_mismatch"),
        ("setup.exe", "disguised_exe.pdf", 415, "unsupported_file_type"),
    ],
)
async def test_rejected_uploads_leave_no_trace(
    api: Api, mongo: Mongo, filename: str, fixture: str, status: int, code: str
) -> None:
    account = await register(api.client, "bad@example.com")

    response = await api.client.post(
        "/api/documents/upload",
        files={"file": (filename, fixture_bytes(fixture))},
        headers=account.headers(),
    )

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert await mongo.db["documents"].count_documents({}) == 0
    assert api.queue.jobs == []
    assert not api.storage_root.exists() or not any(api.storage_root.iterdir())


async def test_oversized_upload_is_413(api: Api) -> None:
    account = await register(api.client, "big@example.com")
    too_big = b"a" * (api.settings.max_upload_bytes + 128 * 1024)

    response = await api.client.post(
        "/api/documents/upload", files={"file": ("big.txt", too_big)}, headers=account.headers()
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


async def test_queue_outage_is_503_and_the_document_is_failed_not_stuck(
    api: Api, mongo: Mongo
) -> None:
    account = await register(api.client, "q@example.com")
    api.app.state.job_queue = RecordingJobQueue(error=ConnectionError("redis down"))

    response = await api.client.post(
        "/api/documents/upload", files={"file": ("a.txt", b"hello")}, headers=account.headers()
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "queue_unavailable"
    document = await mongo.db["documents"].find_one({})
    assert document is not None
    assert document["status"] == DocumentStatus.FAILED
    assert document["error_message"] == "Processing could not be queued. Upload the file again."


async def test_worker_pipeline_completes_and_fails_documents_visible_through_the_api(
    api: Api,
) -> None:
    account = await register(api.client, "flow@example.com")
    good = await upload(api, account, "two_pages.pdf", fixture_bytes("two_pages.pdf"))
    bad = await upload(api, account, "corrupted.pdf", fixture_bytes("corrupted.pdf"))

    await run_queued_jobs(api)

    completed = (
        await api.client.get(f"/api/documents/{good['id']}", headers=account.headers())
    ).json()
    failed = (await api.client.get(f"/api/documents/{bad['id']}", headers=account.headers())).json()
    assert completed["status"] == "COMPLETED"
    assert (completed["page_count"], completed["chunk_count"]) == (2, 2)
    assert completed["processed_at"] is not None
    assert failed["status"] == "FAILED"
    assert failed["error_message"] == "The PDF is corrupted or not a valid PDF file."
    points, _ = await api.qdrant.scroll(COLLECTION, with_payload=True)
    assert {p.payload["document_id"] for p in points} == {good["id"]}  # type: ignore[index]
    assert {p.payload["workspace_id"] for p in points} == {str(account.workspace_id)}  # type: ignore[index]


async def test_list_is_paginated_sorted_filtered_and_scoped_to_the_workspace(api: Api) -> None:
    alice = await register(api.client, "la@example.com")
    bob = await register(api.client, "lb@example.com")
    for name in ("b.txt", "a.txt", "c.txt"):
        await upload(api, alice, name, b"some text")
    await upload(api, bob, "bob.txt", b"bob's text")

    page = await api.client.get(
        "/api/documents", params={"sort": "filename", "page_size": 2}, headers=alice.headers()
    )
    body = page.json()
    assert [d["filename"] for d in body["items"]] == ["a.txt", "b.txt"]
    assert (body["total"], body["pages"], body["page"]) == (3, 2, 1)

    uploaded = await api.client.get(
        "/api/documents", params={"status": "UPLOADED"}, headers=alice.headers()
    )
    assert uploaded.json()["total"] == 3
    completed = await api.client.get(
        "/api/documents", params={"status": "COMPLETED"}, headers=alice.headers()
    )
    assert completed.json()["total"] == 0

    bad_sort = await api.client.get(
        "/api/documents", params={"sort": "storage_key"}, headers=alice.headers()
    )
    assert bad_sort.status_code == 400
    assert bad_sort.json()["error"]["details"] == {"allowed": ["created_at", "filename"]}


async def test_other_users_cannot_read_or_delete_a_document(api: Api) -> None:
    alice = await register(api.client, "ra@example.com")
    bob = await register(api.client, "rb@example.com")
    document = await upload(api, alice, "secret.txt", b"alice only")

    # Bob using his own workspace can't see Alice's document id...
    read = await api.client.get(f"/api/documents/{document['id']}", headers=bob.headers())
    delete = await api.client.delete(f"/api/documents/{document['id']}", headers=bob.headers())
    # ...and can't switch into Alice's workspace.
    foreign = await api.client.get(
        f"/api/documents/{document['id']}", headers=bob.headers(alice.workspace_id)
    )

    assert (read.status_code, read.json()["error"]["code"]) == (404, "document_not_found")
    assert delete.status_code == 404
    assert foreign.status_code == 404
    still_there = await api.client.get(f"/api/documents/{document['id']}", headers=alice.headers())
    assert still_there.status_code == 200


async def test_delete_removes_document_chunks_vectors_and_file(api: Api, mongo: Mongo) -> None:
    account = await register(api.client, "del@example.com")
    document = await upload(api, account, "sample.md", fixture_bytes("sample.md"))
    await run_queued_jobs(api)
    document_id = uuid.UUID(str(document["id"]))
    stored = await mongo.db["documents"].find_one({"_id": document_id})
    assert stored is not None
    storage_key = stored["storage_key"]
    assert await mongo.db["document_chunks"].count_documents({"document_id": document_id}) > 0
    assert (await api.qdrant.count(COLLECTION)).count > 0

    response = await api.client.delete(
        f"/api/documents/{document['id']}", headers=account.headers()
    )

    assert response.status_code == 204
    assert await mongo.db["documents"].find_one({"_id": document_id}) is None
    assert await mongo.db["document_chunks"].count_documents({}) == 0
    assert (await api.qdrant.count(COLLECTION)).count == 0
    assert not (api.storage_root / storage_key).exists()
    assert await mongo.db["activity_logs"].count_documents({"action": "document.deleted"}) == 1


async def test_search_returns_only_the_callers_workspace(api: Api) -> None:
    alice = await register(api.client, "sa@example.com")
    bob = await register(api.client, "sb@example.com")
    alice_doc = await upload(api, alice, "a.txt", b"Refunds for annual plans take 30 days.")
    await upload(api, bob, "b.txt", b"Refunds for annual plans take 30 days.")
    await run_queued_jobs(api)

    response = await api.client.post(
        "/api/search", json={"query": "refunds annual plans"}, headers=alice.headers()
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["document_id"] for r in results] == [alice_doc["id"]]
    assert results[0]["snippet"] == "Refunds for annual plans take 30 days."
    assert results[0]["filename"] == "a.txt"


async def test_search_reports_unavailable_embeddings_as_503(api: Api) -> None:
    from app.ai.embeddings import EmbeddingNotConfiguredError

    account = await register(api.client, "se@example.com")
    api.embedder.error = EmbeddingNotConfiguredError()

    response = await api.client.post("/api/search", json={"query": "x"}, headers=account.headers())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "embeddings_unavailable"


async def test_stats_and_activity_reflect_real_rows(api: Api) -> None:
    account = await register(api.client, "st@example.com", "Sam Taylor")
    await upload(api, account, "good.txt", b"text that indexes")
    await upload(api, account, "bad.pdf", fixture_bytes("corrupted.pdf"))
    await run_queued_jobs(api)

    stats = (await api.client.get("/api/stats", headers=account.headers())).json()
    activity = (await api.client.get("/api/activity", headers=account.headers())).json()

    assert stats["documents"] == {
        "total": 2,
        "by_status": {"UPLOADED": 0, "PROCESSING": 0, "COMPLETED": 1, "FAILED": 1},
    }
    assert stats["tokens"] == {"prompt": 0, "completion": 0, "total": 0}
    actions = [entry["action"] for entry in activity["items"]]
    assert actions.count("document.uploaded") == 2
    assert {"document.processed", "document.failed", "workspace.created"} <= set(actions)
    uploaded = next(e for e in activity["items"] if e["action"] == "document.uploaded")
    assert uploaded["user_name"] == "Sam Taylor"
