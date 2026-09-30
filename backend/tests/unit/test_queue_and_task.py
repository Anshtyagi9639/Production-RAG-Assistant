import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.services.document_processing import Outcome
from app.services.queue import PROCESS_DOCUMENT_TASK, ArqJobQueue, ProcessDocumentJob
from app.workers.tasks import process_document


class RecordingArqRedis:
    """Stands in for arq's Redis client: records enqueue_job calls, dedups by job id."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def enqueue_job(self, name: str, *args: Any, **kwargs: Any) -> object | None:
        if any(call[2]["_job_id"] == kwargs["_job_id"] for call in self.calls):
            return None
        self.calls.append((name, args, kwargs))
        return object()


async def test_enqueue_sends_a_json_payload_with_a_per_document_job_id() -> None:
    redis = RecordingArqRedis()
    job = ProcessDocumentJob(document_id=uuid.uuid4(), workspace_id=uuid.uuid4())

    assert await ArqJobQueue(redis).enqueue_document_processing(job)  # type: ignore[arg-type]

    [(name, args, kwargs)] = redis.calls
    assert name == PROCESS_DOCUMENT_TASK
    assert args == ({"document_id": str(job.document_id), "workspace_id": str(job.workspace_id)},)
    assert kwargs == {"_job_id": f"process-document:{job.document_id}"}


async def test_enqueueing_the_same_document_twice_is_a_no_op() -> None:
    redis = RecordingArqRedis()
    queue = ArqJobQueue(redis)  # type: ignore[arg-type]
    job = ProcessDocumentJob(document_id=uuid.uuid4(), workspace_id=uuid.uuid4())

    assert await queue.enqueue_document_processing(job) is True
    assert await queue.enqueue_document_processing(job) is False
    assert len(redis.calls) == 1


def test_valid_payload_is_accepted() -> None:
    document_id, workspace_id = uuid.uuid4(), uuid.uuid4()

    job = ProcessDocumentJob.model_validate(
        {"document_id": str(document_id), "workspace_id": str(workspace_id)}
    )

    assert (job.document_id, job.workspace_id) == (document_id, workspace_id)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"document_id": str(uuid.uuid4())},
        {"document_id": "not-a-uuid", "workspace_id": str(uuid.uuid4())},
        {"document_id": str(uuid.uuid4()), "workspace_id": str(uuid.uuid4()), "extra": 1},
        None,
        "a string",
    ],
)
def test_invalid_payloads_are_rejected(payload: object) -> None:
    with pytest.raises(ValidationError):
        ProcessDocumentJob.model_validate(payload)


class RecordingProcessor:
    def __init__(self) -> None:
        self.jobs: list[ProcessDocumentJob] = []

    async def process(self, job: ProcessDocumentJob) -> Outcome:
        self.jobs.append(job)
        return Outcome.COMPLETED


async def test_task_drops_malformed_payloads_without_touching_documents() -> None:
    processor = RecordingProcessor()

    result = await process_document(
        {"processor": processor, "job_id": "j1"}, {"document_id": "nope"}
    )

    assert result == "rejected"
    assert processor.jobs == []


async def test_task_hands_valid_jobs_to_the_processor() -> None:
    processor = RecordingProcessor()
    job = ProcessDocumentJob(document_id=uuid.uuid4(), workspace_id=uuid.uuid4())

    result = await process_document({"processor": processor}, job.model_dump(mode="json"))

    assert result == "completed"
    assert processor.jobs == [job]
