"""Indexing and retrieval against qdrant-client's local in-process mode (not a Qdrant server)."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.ai.retrieval import retrieve, workspace_filter
from app.rag import indexing
from app.rag.chunking import chunk_pages
from app.rag.extraction import Page
from app.rag.indexing import COLLECTION, VectorIndex, VectorIndexError, ensure_collection
from tests.fakes import TEST_DIMENSIONS, FakeEmbedder

embedder = FakeEmbedder()


async def _index(
    qdrant: AsyncQdrantClient, workspace_id: uuid.UUID, texts: list[str], filename: str = "a.pdf"
) -> uuid.UUID:
    document_id = uuid.uuid4()
    chunks = chunk_pages([Page(n, text) for n, text in enumerate(texts, 1)], document_id)
    await VectorIndex(qdrant).replace_document(
        document_id=document_id,
        workspace_id=workspace_id,
        filename=filename,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        chunks=chunks,
        vectors=[embedder.vector(chunk.text) for chunk in chunks],
    )
    return document_id


async def _search(
    qdrant: AsyncQdrantClient, workspace_id: uuid.UUID, query: str, **kwargs: object
) -> list[uuid.UUID]:
    chunks = await retrieve(
        qdrant,
        embedder.vector(query),
        workspace_id=workspace_id,
        top_k=10,
        score_threshold=kwargs.pop("score_threshold", 0.0),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )
    return [chunk.document_id for chunk in chunks]


async def test_points_carry_the_full_payload(qdrant: AsyncQdrantClient) -> None:
    workspace_id = uuid.uuid4()
    document_id = await _index(qdrant, workspace_id, ["Refunds take 30 days."], "policy.pdf")

    [point], _ = await qdrant.scroll(COLLECTION, with_payload=True)

    assert point.payload == {
        "document_id": str(document_id),
        "workspace_id": str(workspace_id),
        "filename": "policy.pdf",
        "page": 1,
        "chunk_index": 0,
        "source": "policy.pdf, page 1",
        "created_at": "2026-09-01T00:00:00+00:00",
        "text": "Refunds take 30 days.",
    }


async def test_search_never_returns_another_workspaces_chunks(qdrant: AsyncQdrantClient) -> None:
    workspace_a, workspace_b = uuid.uuid4(), uuid.uuid4()
    document_a = await _index(qdrant, workspace_a, ["Refund policy: refunds within 30 days."])
    document_b = await _index(qdrant, workspace_b, ["Refund policy: refunds within 30 days."])

    assert await _search(qdrant, workspace_a, "refund policy") == [document_a]
    assert await _search(qdrant, workspace_b, "refund policy") == [document_b]
    assert await _search(qdrant, uuid.uuid4(), "refund policy") == []


def test_every_filter_includes_the_workspace_condition() -> None:
    workspace_id = uuid.uuid4()

    conditions = workspace_filter(workspace_id, [uuid.uuid4()]).must

    assert isinstance(conditions, list)
    keys = [condition.key for condition in conditions]  # type: ignore[union-attr]
    assert keys == ["workspace_id", "document_id"]
    assert conditions[0].match.value == str(workspace_id)  # type: ignore[union-attr]


async def test_document_filter_narrows_within_the_workspace(qdrant: AsyncQdrantClient) -> None:
    workspace_id = uuid.uuid4()
    first = await _index(qdrant, workspace_id, ["Travel expenses are reimbursed."])
    second = await _index(qdrant, workspace_id, ["Travel expenses need receipts."])

    assert set(await _search(qdrant, workspace_id, "travel expenses")) == {first, second}
    assert await _search(qdrant, workspace_id, "travel expenses", document_ids=[second]) == [second]


async def test_score_threshold_drops_unrelated_chunks(qdrant: AsyncQdrantClient) -> None:
    workspace_id = uuid.uuid4()
    await _index(qdrant, workspace_id, ["Payroll runs on the last working day."])

    assert await _search(qdrant, workspace_id, "quantum chromodynamics", score_threshold=0.5) == []


async def test_reindexing_a_document_replaces_its_points(qdrant: AsyncQdrantClient) -> None:
    workspace_id = uuid.uuid4()
    document_id = uuid.uuid4()
    index = VectorIndex(qdrant)
    for texts in (["one", "two", "three"], ["only one now"]):
        chunks = chunk_pages([Page(n, t) for n, t in enumerate(texts, 1)], document_id)
        await index.replace_document(
            document_id=document_id,
            workspace_id=workspace_id,
            filename="a.pdf",
            created_at=datetime.now(UTC),
            chunks=chunks,
            vectors=[embedder.vector(c.text) for c in chunks],
        )

    points, _ = await qdrant.scroll(COLLECTION, with_payload=True)
    assert [p.payload["text"] for p in points] == ["only one now"]  # type: ignore[index]


async def test_delete_removes_only_that_document(qdrant: AsyncQdrantClient) -> None:
    workspace_id = uuid.uuid4()
    keep = await _index(qdrant, workspace_id, ["keep me"])
    remove = await _index(qdrant, workspace_id, ["remove me"])

    await VectorIndex(qdrant).delete_document(remove, workspace_id)

    points, _ = await qdrant.scroll(COLLECTION, with_payload=True)
    assert {p.payload["document_id"] for p in points} == {str(keep)}  # type: ignore[index]


async def test_delete_with_the_wrong_workspace_removes_nothing(qdrant: AsyncQdrantClient) -> None:
    workspace_id = uuid.uuid4()
    document_id = await _index(qdrant, workspace_id, ["protected"])

    await VectorIndex(qdrant).delete_document(document_id, uuid.uuid4())

    assert (await qdrant.count(COLLECTION)).count == 1


async def test_collection_bootstrap_is_idempotent(qdrant: AsyncQdrantClient) -> None:
    await ensure_collection(qdrant, TEST_DIMENSIONS)

    info = await qdrant.get_collection(COLLECTION)
    assert info.config.params.vectors.size == TEST_DIMENSIONS  # type: ignore[union-attr]


async def test_qdrant_failures_become_a_user_facing_error() -> None:
    client = AsyncQdrantClient(location=":memory:")  # no collection created

    with pytest.raises(VectorIndexError, match="search index is unavailable"):
        await retrieve(
            client, [0.1] * TEST_DIMENSIONS, workspace_id=uuid.uuid4(), top_k=3, score_threshold=0
        )
    await client.close()


class FlakyQdrant:
    """Wraps the in-process client; the first `failures` writes raise `error`."""

    def __init__(self, client: AsyncQdrantClient, failures: int, error: Exception) -> None:
        self._client = client
        self.failures = failures
        self.error = error
        self.calls = 0

    async def delete(self, *args: object, **kwargs: object) -> object:
        self.calls += 1
        if self.failures > 0:
            self.failures -= 1
            raise self.error
        return await self._client.delete(*args, **kwargs)  # type: ignore[arg-type]

    async def upsert(self, *args: object, **kwargs: object) -> object:
        return await self._client.upsert(*args, **kwargs)  # type: ignore[arg-type]


def _transport_error() -> Exception:
    return ResponseHandlingException(httpx.RemoteProtocolError("Server disconnected"))


@pytest.fixture
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(indexing, "RETRY_BASE_DELAY_SECONDS", 0)


@pytest.mark.usefixtures("no_backoff")
async def test_a_dropped_connection_is_retried_and_the_write_succeeds(
    qdrant: AsyncQdrantClient,
) -> None:
    flaky = FlakyQdrant(qdrant, failures=1, error=_transport_error())
    workspace_id = uuid.uuid4()
    chunks = chunk_pages([Page(1, "Refunds take 30 days.")], uuid.uuid4())

    await VectorIndex(flaky).replace_document(  # type: ignore[arg-type]
        document_id=chunks[0].id,
        workspace_id=workspace_id,
        filename="a.md",
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        chunks=chunks,
        vectors=[embedder.vector(c.text) for c in chunks],
    )

    assert flaky.calls == 2
    assert (await qdrant.count(COLLECTION)).count == 1


@pytest.mark.usefixtures("no_backoff")
async def test_persistent_transient_failures_give_up_after_the_last_attempt(
    qdrant: AsyncQdrantClient,
) -> None:
    flaky = FlakyQdrant(qdrant, failures=10, error=_transport_error())

    with pytest.raises(VectorIndexError):
        await VectorIndex(flaky).delete_document(uuid.uuid4(), uuid.uuid4())  # type: ignore[arg-type]
    assert flaky.calls == indexing.MAX_ATTEMPTS


@pytest.mark.usefixtures("no_backoff")
async def test_client_errors_are_not_retried(qdrant: AsyncQdrantClient) -> None:
    bad_request = UnexpectedResponse(400, "Bad Request", b"{}", httpx.Headers())
    flaky = FlakyQdrant(qdrant, failures=10, error=bad_request)

    with pytest.raises(VectorIndexError):
        await VectorIndex(flaky).delete_document(uuid.uuid4(), uuid.uuid4())  # type: ignore[arg-type]
    assert flaky.calls == 1


@pytest.mark.parametrize(
    ("error", "transient"),
    [
        (_transport_error(), True),
        (UnexpectedResponse(503, "Unavailable", b"", httpx.Headers()), True),
        (UnexpectedResponse(429, "Too Many Requests", b"", httpx.Headers()), True),
        (UnexpectedResponse(404, "Not Found", b"", httpx.Headers()), False),
        (ValueError("bad payload"), False),
    ],
)
def test_only_transient_errors_are_retried(error: Exception, transient: bool) -> None:
    assert indexing.is_transient(error) is transient
