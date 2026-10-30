"""The worker's orchestration: status transitions, failure reasons, and vector cleanup.

The document store is an in-memory double of MongoDocumentStore (whose transitions are
tested against MongoDB Atlas in tests/integration). Files, extraction, chunking and the Qdrant
index are real; the embedding provider is FakeEmbedder.
"""

import uuid
from pathlib import Path

import pytest
from qdrant_client import AsyncQdrantClient

from app.ai.embeddings import EmbeddingNotConfiguredError
from app.models.enums import DocumentStatus
from app.rag.indexing import COLLECTION, VectorIndex, VectorIndexError
from app.services.document_processing import INTERNAL_FAILURE_REASON, DocumentProcessor, Outcome
from app.services.queue import ProcessDocumentJob
from app.storage.local import LocalStorage
from tests.conftest import fixture_bytes
from tests.fakes import FakeEmbedder, InMemoryDocumentStore, StoredDocument

UPLOADED, PROCESSING, COMPLETED, FAILED = (
    DocumentStatus.UPLOADED,
    DocumentStatus.PROCESSING,
    DocumentStatus.COMPLETED,
    DocumentStatus.FAILED,
)


class Harness:
    def __init__(self, tmp_path: Path, qdrant: AsyncQdrantClient) -> None:
        self.store = InMemoryDocumentStore()
        self.storage = LocalStorage(tmp_path)
        self.embedder = FakeEmbedder()
        self.qdrant = qdrant
        self.index = VectorIndex(qdrant)
        self.workspace_id = uuid.uuid4()

    def processor(self, index: VectorIndex | None = None) -> DocumentProcessor:
        return DocumentProcessor(
            store=self.store,
            storage=self.storage,
            embedder=self.embedder,
            index=index or self.index,
            embedding_batch_size=16,
            embedding_max_attempts=2,
        )

    async def upload(self, fixture: str, *, store_file: bool = True) -> StoredDocument:
        extension = fixture[fixture.index(".") :]
        key = f"{uuid.uuid4().hex}{extension}"
        if store_file:
            await self.storage.save(key, fixture_bytes(fixture))
        return self.store.add(
            StoredDocument(
                id=uuid.uuid4(),
                workspace_id=self.workspace_id,
                filename=fixture,
                storage_key=key,
            )
        )

    def job(
        self, document: StoredDocument, workspace_id: uuid.UUID | None = None
    ) -> ProcessDocumentJob:
        return ProcessDocumentJob(
            document_id=document.id, workspace_id=workspace_id or document.workspace_id
        )

    async def point_count(self) -> int:
        return (await self.qdrant.count(COLLECTION)).count


@pytest.fixture
def harness(tmp_path: Path, qdrant: AsyncQdrantClient) -> Harness:
    return Harness(tmp_path, qdrant)


@pytest.mark.parametrize(
    ("fixture", "pages"),
    [
        ("two_pages.pdf", [1, 2]),
        ("sample.docx", [None]),
        ("sample.txt", [None]),
        ("sample.md", [None]),
    ],
)
async def test_valid_documents_go_uploaded_processing_completed(
    harness: Harness, fixture: str, pages: list[int | None]
) -> None:
    document = await harness.upload(fixture)

    outcome = await harness.processor().process(harness.job(document))

    assert outcome == Outcome.COMPLETED
    assert document.history == [UPLOADED, PROCESSING, COMPLETED]
    assert document.error_message is None
    assert [chunk.page for chunk in document.chunks] == pages
    points, _ = await harness.qdrant.scroll(COLLECTION, with_payload=True, limit=100)
    assert len(points) == len(document.chunks)
    assert {p.payload["workspace_id"] for p in points} == {str(harness.workspace_id)}  # type: ignore[index]
    assert {p.id for p in points} == {str(chunk.id) for chunk in document.chunks}


async def test_pdf_page_count_is_recorded(harness: Harness) -> None:
    document = await harness.upload("two_pages.pdf")

    await harness.processor().process(harness.job(document))

    assert document.page_count == 2


@pytest.mark.parametrize(
    ("fixture", "reason"),
    [
        ("corrupted.pdf", "The PDF is corrupted or not a valid PDF file."),
        ("encrypted.pdf", "The PDF is password-protected."),
        ("no_text.pdf", "No extractable text was found (a PDF may be a scanned image)."),
    ],
)
async def test_malformed_documents_end_failed_with_a_readable_reason(
    harness: Harness, fixture: str, reason: str
) -> None:
    document = await harness.upload(fixture)

    outcome = await harness.processor().process(harness.job(document))

    assert outcome == Outcome.FAILED
    assert document.history == [UPLOADED, PROCESSING, FAILED]
    assert document.error_message == reason
    assert await harness.point_count() == 0


async def test_missing_stored_file_ends_failed(harness: Harness) -> None:
    document = await harness.upload("sample.txt", store_file=False)

    await harness.processor().process(harness.job(document))

    assert document.status == FAILED
    assert (
        document.error_message
        == "The uploaded file could not be found in storage. Upload it again."
    )


async def test_embedding_outage_ends_failed_after_retries(harness: Harness) -> None:
    harness.embedder.fail_times = 10
    document = await harness.upload("sample.txt")

    await harness.processor().process(harness.job(document))

    assert document.status == FAILED
    assert (
        document.error_message
        == "The embedding service failed to respond. Try uploading again later."
    )
    assert len(harness.embedder.document_calls) == 2  # embedding_max_attempts
    assert await harness.point_count() == 0


async def test_transient_embedding_failure_is_retried_and_completes(harness: Harness) -> None:
    harness.embedder.fail_times = 1
    document = await harness.upload("sample.txt")

    assert await harness.processor().process(harness.job(document)) == Outcome.COMPLETED


async def test_missing_openai_key_is_reported_as_the_reason(harness: Harness) -> None:
    harness.embedder.error = EmbeddingNotConfiguredError()
    document = await harness.upload("sample.md")

    await harness.processor().process(harness.job(document))

    assert document.status == FAILED
    assert "OPENAI_API_KEY is not set" in (document.error_message or "")


async def test_unexpected_errors_fail_the_document_without_leaking_details(
    harness: Harness,
) -> None:
    harness.embedder.error = RuntimeError("provider said: key sk-live-123 is invalid")
    document = await harness.upload("sample.txt")

    outcome = await harness.processor().process(harness.job(document))

    assert outcome == Outcome.FAILED
    assert document.status == FAILED
    assert document.error_message == INTERNAL_FAILURE_REASON


class BrokenIndex(VectorIndex):
    async def replace_document(self, **kwargs: object) -> None:
        raise VectorIndexError


async def test_qdrant_outage_ends_failed(harness: Harness) -> None:
    document = await harness.upload("sample.txt")

    await harness.processor(BrokenIndex(harness.qdrant)).process(harness.job(document))

    assert document.status == FAILED
    assert document.error_message == "The search index is unavailable. Try again later."


async def test_database_error_after_indexing_removes_vectors_and_fails(harness: Harness) -> None:
    harness.store.complete_error = ConnectionError("database went away")
    document = await harness.upload("sample.txt")

    outcome = await harness.processor().process(harness.job(document))

    assert outcome == Outcome.FAILED
    assert document.status == FAILED
    assert await harness.point_count() == 0


async def test_if_marking_failed_is_impossible_the_error_propagates_for_a_retry(
    harness: Harness,
) -> None:
    harness.embedder.error = RuntimeError("boom")
    harness.store.fail_error = ConnectionError("database down")
    document = await harness.upload("sample.txt")

    with pytest.raises(ConnectionError):
        await harness.processor().process(harness.job(document))
    # Still PROCESSING: arq retries the job, and claim() accepts PROCESSING documents.
    assert document.status == PROCESSING


async def test_retried_job_for_a_processing_document_completes(harness: Harness) -> None:
    document = await harness.upload("sample.txt")
    document.status = PROCESSING

    assert await harness.processor().process(harness.job(document)) == Outcome.COMPLETED
    assert document.status == COMPLETED


async def test_a_job_naming_another_workspace_is_skipped(harness: Harness) -> None:
    document = await harness.upload("sample.txt")

    outcome = await harness.processor().process(harness.job(document, workspace_id=uuid.uuid4()))

    assert outcome == Outcome.SKIPPED
    assert document.history == [UPLOADED]
    assert harness.embedder.document_calls == []
    assert await harness.point_count() == 0


async def test_unknown_document_is_skipped(harness: Harness) -> None:
    job = ProcessDocumentJob(document_id=uuid.uuid4(), workspace_id=harness.workspace_id)

    assert await harness.processor().process(job) == Outcome.SKIPPED


@pytest.mark.parametrize("status", [COMPLETED, FAILED])
async def test_duplicate_jobs_for_finished_documents_are_skipped(
    harness: Harness, status: DocumentStatus
) -> None:
    document = await harness.upload("sample.txt")
    document.status = status

    assert await harness.processor().process(harness.job(document)) == Outcome.SKIPPED
    assert harness.embedder.document_calls == []


async def test_document_deleted_during_processing_leaves_no_vectors(harness: Harness) -> None:
    document = await harness.upload("sample.txt")
    processor = harness.processor()
    original_complete = harness.store.complete

    async def delete_then_complete(*args: object, **kwargs: object) -> bool:
        del harness.store.documents[document.id]
        return await original_complete(*args, **kwargs)  # type: ignore[arg-type]

    harness.store.complete = delete_then_complete  # type: ignore[method-assign]

    assert await processor.process(harness.job(document)) == Outcome.SKIPPED
    assert await harness.point_count() == 0
