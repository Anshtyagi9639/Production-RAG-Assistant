import uuid
from typing import Protocol

from arq.connections import ArqRedis
from pydantic import BaseModel, ConfigDict

PROCESS_DOCUMENT_TASK = "process_document"


class ProcessDocumentJob(BaseModel):
    """The payload of a document-processing job. Validated again by the worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: uuid.UUID
    workspace_id: uuid.UUID


class JobQueue(Protocol):
    async def enqueue_document_processing(self, job: ProcessDocumentJob) -> bool:
        """Queue the job. Returns False if a job for this document already exists."""
        ...


class ArqJobQueue:
    """Jobs in Redis via arq. The job id is derived from the document id, so a document can't
    be queued twice while a job for it is pending or its result is still kept."""

    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    async def enqueue_document_processing(self, job: ProcessDocumentJob) -> bool:
        queued = await self._redis.enqueue_job(
            PROCESS_DOCUMENT_TASK,
            job.model_dump(mode="json"),
            _job_id=f"process-document:{job.document_id}",
        )
        return queued is not None
