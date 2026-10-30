"""Test doubles for external boundaries only (embedding provider, LLM, job queue, document store).

Nothing here is used by application code.
"""

import hashlib
import math
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.ai.embeddings import EmbeddingError
from app.ai.llm import LLMMessage, LLMResult
from app.models.enums import DocumentStatus
from app.rag.chunking import Chunk
from app.services.document_processing import ClaimedDocument
from app.services.queue import AgentRunJob, ProcessDocumentJob

TEST_DIMENSIONS = 64


class FakeEmbedder:
    """Deterministic hashed bag-of-words vectors, so texts sharing words score higher.

    `fail_times` makes the next N calls raise EmbeddingError (a transient provider failure);
    `error` makes every call raise that exception instead.
    """

    def __init__(
        self,
        dimensions: int = TEST_DIMENSIONS,
        fail_times: int = 0,
        error: Exception | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.fail_times = fail_times
        self.error = error
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def vector(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        for word in re.findall(r"\w+", text.lower()):
            values[int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dimensions] += 1.0
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values] if any(values) else [1.0] + [0.0] * (self.dimensions - 1)

    def _maybe_fail(self) -> None:
        if self.error is not None:
            raise self.error
        if self.fail_times > 0:
            self.fail_times -= 1
            raise EmbeddingError

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        self._maybe_fail()
        return [self.vector(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        self._maybe_fail()
        return self.vector(text)


Reply = str | Exception


class FakeLLM:
    """Scripted model. `reply` is a fixed answer, a list consumed in order, or a function of
    the messages (e.g. routing on the system prompt). Records every call."""

    def __init__(
        self, reply: Reply | list[Reply] | Callable[[list[LLMMessage]], Reply] = "Answer [1]."
    ) -> None:
        self.reply = reply
        self.calls: list[list[LLMMessage]] = []

    async def complete(
        self, messages: list[LLMMessage], *, max_tokens: int, json_mode: bool = False
    ) -> LLMResult:
        self.calls.append(messages)
        if callable(self.reply):
            reply = self.reply(messages)
        elif isinstance(self.reply, list):
            reply = self.reply.pop(0)
        else:
            reply = self.reply
        if isinstance(reply, Exception):
            raise reply
        return LLMResult(text=reply, prompt_tokens=100, completion_tokens=20)


class RecordingJobQueue:
    def __init__(self, error: Exception | None = None) -> None:
        self.jobs: list[ProcessDocumentJob] = []
        self.agent_jobs: list[AgentRunJob] = []
        self.error = error

    async def enqueue_document_processing(self, job: ProcessDocumentJob) -> bool:
        if self.error is not None:
            raise self.error
        if any(queued.document_id == job.document_id for queued in self.jobs):
            return False
        self.jobs.append(job)
        return True

    async def enqueue_agent_run(self, job: AgentRunJob) -> bool:
        if self.error is not None:
            raise self.error
        if any(queued.run_id == job.run_id for queued in self.agent_jobs):
            return False
        self.agent_jobs.append(job)
        return True


@dataclass
class StoredDocument:
    id: uuid.UUID
    workspace_id: uuid.UUID
    filename: str
    storage_key: str
    status: DocumentStatus = DocumentStatus.UPLOADED
    error_message: str | None = None
    page_count: int | None = None
    chunks: list[Chunk] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    history: list[DocumentStatus] = field(default_factory=list)


class InMemoryDocumentStore:
    """Mirrors MongoDocumentStore's transition rules; the MongoDB version is covered by
    tests/integration/test_worker_pipeline.py against MongoDB Atlas."""

    def __init__(self) -> None:
        self.documents: dict[uuid.UUID, StoredDocument] = {}
        self.complete_error: Exception | None = None
        self.fail_error: Exception | None = None

    def add(self, document: StoredDocument) -> StoredDocument:
        document.history.append(document.status)
        self.documents[document.id] = document
        return document

    def _find(self, document_id: uuid.UUID, workspace_id: uuid.UUID) -> StoredDocument | None:
        document = self.documents.get(document_id)
        return document if document and document.workspace_id == workspace_id else None

    def _set(self, document: StoredDocument, status: DocumentStatus) -> None:
        document.status = status
        document.history.append(status)

    async def claim(self, job: ProcessDocumentJob) -> ClaimedDocument | None:
        document = self._find(job.document_id, job.workspace_id)
        if document is None or document.status not in {
            DocumentStatus.UPLOADED,
            DocumentStatus.PROCESSING,
        }:
            return None
        self._set(document, DocumentStatus.PROCESSING)
        return ClaimedDocument(
            id=document.id,
            workspace_id=document.workspace_id,
            filename=document.filename,
            storage_key=document.storage_key,
            created_at=document.created_at,
        )

    async def complete(
        self, document: ClaimedDocument, chunks: list[Chunk], page_count: int | None
    ) -> bool:
        if self.complete_error is not None:
            raise self.complete_error
        stored = self._find(document.id, document.workspace_id)
        if stored is None:
            return False
        stored.chunks = list(chunks)
        stored.page_count = page_count
        self._set(stored, DocumentStatus.COMPLETED)
        return True

    async def fail(self, document: ClaimedDocument, reason: str) -> None:
        if self.fail_error is not None:
            raise self.fail_error
        stored = self._find(document.id, document.workspace_id)
        if stored is not None:
            stored.error_message = reason
            self._set(stored, DocumentStatus.FAILED)
