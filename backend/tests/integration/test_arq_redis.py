"""The real queue: arq over Redis, consumed by an arq Worker in burst mode.

Needs Redis at REDIS_URL and MongoDB Atlas. Not faked: if Redis is down, this test fails.
"""

import signal
import uuid

import pytest
from arq import Worker, func
from arq.connections import ArqRedis
from qdrant_client import AsyncQdrantClient

from app.db.mongo import Mongo
from app.models import Document
from app.models.enums import DocumentStatus
from app.rag.indexing import VectorIndex
from app.repositories.document_store import MongoDocumentStore
from app.services.document_processing import DocumentProcessor
from app.services.queue import PROCESS_DOCUMENT_TASK, ArqJobQueue, ProcessDocumentJob
from app.storage.local import LocalStorage
from app.workers.tasks import process_document
from tests.conftest import fixture_bytes
from tests.fakes import FakeEmbedder
from tests.integration.conftest import live_settings
from tests.integration.factories import add_user, add_workspace

pytestmark = pytest.mark.integration


async def test_job_goes_through_redis_to_the_worker_and_completes(
    mongo: Mongo,
    qdrant: AsyncQdrantClient,
    tmp_path: object,
) -> None:
    redis = ArqRedis.from_url(live_settings().redis_url)
    queue_name = f"test-queue-{uuid.uuid4().hex}"
    storage = LocalStorage(tmp_path / "uploads")  # type: ignore[operator]
    owner = await add_user(mongo)
    workspace = await add_workspace(mongo, owner)
    key = f"{uuid.uuid4().hex}.txt"
    await storage.save(key, fixture_bytes("sample.txt"))
    document = Document(
        workspace_id=workspace.id,
        uploaded_by_id=owner.id,
        filename="sample.txt",
        storage_key=key,
        content_type="text/plain",
        size_bytes=len(fixture_bytes("sample.txt")),
    )
    await mongo.db["documents"].insert_one(document.to_document())

    redis.default_queue_name = queue_name
    queue = ArqJobQueue(redis)
    job = ProcessDocumentJob(document_id=document.id, workspace_id=workspace.id)
    assert await queue.enqueue_document_processing(job) is True
    assert await queue.enqueue_document_processing(job) is False  # deduplicated by job id

    processor = DocumentProcessor(
        store=MongoDocumentStore(mongo),
        storage=storage,
        embedder=FakeEmbedder(),
        index=VectorIndex(qdrant),
        embedding_batch_size=16,
        embedding_max_attempts=2,
    )
    worker = Worker(
        functions=[func(process_document, name=PROCESS_DOCUMENT_TASK)],
        redis_pool=redis,
        queue_name=queue_name,
        burst=True,
        poll_delay=0.1,
        ctx={"processor": processor},
        handle_signals=False,
    )
    try:
        await worker.async_run()
        assert (worker.jobs_complete, worker.jobs_failed) == (1, 0)
    finally:
        if hasattr(signal, "SIGUSR1"):
            await worker.close()
        else:
            # arq's close() raises SIGUSR1 to cancel running jobs, and Windows has no SIGUSR1.
            # In burst mode no job is running, so do the rest of close() directly.
            await worker.pool.delete(worker.health_check_key)
            await worker.pool.aclose()

    processed = await mongo.db["documents"].find_one({"_id": document.id})
    assert processed is not None
    assert processed["status"] == DocumentStatus.COMPLETED
    assert processed["chunk_count"] == 1
