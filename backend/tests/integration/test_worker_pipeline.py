"""MongoDocumentStore status transitions against MongoDB Atlas, with real transactions."""

import uuid
from typing import Any

import pytest
from pymongo.errors import BulkWriteError

from app.db.mongo import Mongo
from app.models import Document
from app.models.enums import DocumentStatus
from app.rag.chunking import Chunk, chunk_id
from app.repositories.document_store import MongoDocumentStore
from app.services.document_processing import ClaimedDocument
from app.services.queue import ProcessDocumentJob
from tests.integration.factories import add_document, add_user, add_workspace

pytestmark = pytest.mark.integration


async def _document(mongo: Mongo) -> Document:
    owner = await add_user(mongo)
    workspace = await add_workspace(mongo, owner)
    return await add_document(mongo, workspace, owner)


def _chunks(document_id: uuid.UUID, count: int) -> list[Chunk]:
    return [
        Chunk(id=chunk_id(document_id, n), index=n, page=1, text=f"chunk {n}", token_count=2)
        for n in range(count)
    ]


async def _reload(mongo: Mongo, document: Document) -> dict[str, Any]:
    stored = await mongo.db["documents"].find_one({"_id": document.id})
    assert stored is not None
    return stored


async def _claim(store: MongoDocumentStore, document: Document) -> ClaimedDocument:
    claimed = await store.claim(
        ProcessDocumentJob(document_id=document.id, workspace_id=document.workspace_id)
    )
    assert claimed is not None
    return claimed


async def test_claim_moves_uploaded_to_processing(mongo: Mongo) -> None:
    document = await _document(mongo)
    store = MongoDocumentStore(mongo)

    claimed = await _claim(store, document)

    assert (claimed.id, claimed.storage_key) == (document.id, document.storage_key)
    assert (await _reload(mongo, document))["status"] == DocumentStatus.PROCESSING


async def test_claim_refuses_other_workspaces_and_finished_documents(mongo: Mongo) -> None:
    document = await _document(mongo)
    store = MongoDocumentStore(mongo)

    assert (
        await store.claim(ProcessDocumentJob(document_id=document.id, workspace_id=uuid.uuid4()))
        is None
    )
    assert (await _reload(mongo, document))["status"] == DocumentStatus.UPLOADED

    await mongo.db["documents"].update_one(
        {"_id": document.id}, {"$set": {"status": DocumentStatus.COMPLETED.value}}
    )
    assert (
        await store.claim(
            ProcessDocumentJob(document_id=document.id, workspace_id=document.workspace_id)
        )
        is None
    )


async def test_complete_persists_chunks_counts_and_activity(mongo: Mongo) -> None:
    document = await _document(mongo)
    store = MongoDocumentStore(mongo)
    claimed = await _claim(store, document)

    assert await store.complete(claimed, _chunks(document.id, 3), page_count=2)
    # Re-processing replaces the chunks instead of duplicating them.
    assert await store.complete(claimed, _chunks(document.id, 2), page_count=2)

    fresh = await _reload(mongo, document)
    assert fresh["status"] == DocumentStatus.COMPLETED
    assert (fresh["chunk_count"], fresh["page_count"]) == (2, 2)
    assert fresh["processed_at"] is not None
    chunks = await mongo.db["document_chunks"].find({}).sort("chunk_index", 1).to_list()
    assert [(c["_id"], c["workspace_id"]) for c in chunks] == [
        (chunk_id(document.id, n), document.workspace_id) for n in range(2)
    ]
    assert await mongo.db["activity_logs"].count_documents({"action": "document.processed"}) == 2


async def test_failed_completion_rolls_back_everything(mongo: Mongo) -> None:
    document = await _document(mongo)
    store = MongoDocumentStore(mongo)
    claimed = await _claim(store, document)
    duplicate_index = [
        *_chunks(document.id, 1),
        Chunk(id=uuid.uuid4(), index=0, page=1, text="clash", token_count=1),
    ]

    with pytest.raises(BulkWriteError):
        await store.complete(claimed, duplicate_index, page_count=1)

    fresh = await _reload(mongo, document)
    assert fresh["status"] == DocumentStatus.PROCESSING
    assert fresh.get("chunk_count") is None
    assert await mongo.db["document_chunks"].count_documents({}) == 0
    assert await mongo.db["activity_logs"].count_documents({}) == 0


async def test_fail_persists_the_reason_and_activity(mongo: Mongo) -> None:
    document = await _document(mongo)
    store = MongoDocumentStore(mongo)
    claimed = await _claim(store, document)

    await store.fail(claimed, "The PDF is password-protected." + " x" * 2000)

    fresh = await _reload(mongo, document)
    assert fresh["status"] == DocumentStatus.FAILED
    assert fresh["error_message"].startswith("The PDF is password-protected.")
    assert len(fresh["error_message"]) == 1000
    entry = await mongo.db["activity_logs"].find_one({"action": "document.failed"})
    assert entry is not None
    assert entry["user_id"] is None


async def test_complete_after_delete_reports_false(mongo: Mongo) -> None:
    document = await _document(mongo)
    store = MongoDocumentStore(mongo)
    claimed = await _claim(store, document)
    await mongo.db["documents"].delete_one({"_id": document.id})

    assert await store.complete(claimed, _chunks(document.id, 1), page_count=1) is False
    assert await mongo.db["document_chunks"].count_documents({}) == 0
