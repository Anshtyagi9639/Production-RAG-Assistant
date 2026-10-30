import logging
import uuid
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from arq.connections import ArqRedis

PROCESS_DOCUMENT_TASK = "process_document"
RUN_AGENT_TASK = "run_agent"

logger = logging.getLogger(__name__)


class ProcessDocumentJob(BaseModel):
    """The payload of a document-processing job. Validated again by the worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: uuid.UUID
    workspace_id: uuid.UUID


class AgentRunJob(BaseModel):
    """The payload of an agent-run job. Validated again by the worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: uuid.UUID
    workspace_id: uuid.UUID


class JobQueue(Protocol):
    async def enqueue_document_processing(self, job: ProcessDocumentJob) -> bool:
        """Queue the job. Returns False if a job for this document already exists."""
        ...

    async def enqueue_agent_run(self, job: AgentRunJob) -> bool:
        """Queue the run. Returns False if a job for this run already exists."""
        ...


class ArqJobQueue:
    """Jobs in Redis via arq. The job id is derived from the document id, so a document can't
    be queued twice while a job for it is pending or its result is still kept."""

    def __init__(self, redis: "ArqRedis") -> None:
        self._redis = redis

    async def enqueue_document_processing(self, job: ProcessDocumentJob) -> bool:
        queued = await self._redis.enqueue_job(
            PROCESS_DOCUMENT_TASK,
            job.model_dump(mode="json"),
            _job_id=f"process-document:{job.document_id}",
        )
        return queued is not None

    async def enqueue_agent_run(self, job: AgentRunJob) -> bool:
        queued = await self._redis.enqueue_job(
            RUN_AGENT_TASK, job.model_dump(mode="json"), _job_id=f"agent-run:{job.run_id}"
        )
        return queued is not None

    async def close(self) -> None:
        await self._redis.aclose()


def create_arq_job_queue(redis_url: str) -> ArqJobQueue | None:
    """The API's job queue, or None when arq is not installed.

    TODO: ARQ startup dependency is temporarily disabled for local development because ARQ
    is not installed in the current environment. Restore this dependency before enabling
    Redis-backed background processing. (arq is still declared in requirements.txt; the
    import is deferred to here so the API can start without it, and uploads return 503
    while no queue is available.)
    """
    try:
        from arq.connections import ArqRedis
    except ImportError:
        logger.warning(
            "job_queue_unavailable",
            extra={"reason": "arq is not installed; background document processing is off"},
        )
        return None
    from app.db.redis import REDIS_HEALTH_CHECK_SECONDS, REDIS_RETRY_ON, redis_retry

    # arq stores pickled job payloads, so it needs its own client without response decoding.
    # Connections are opened lazily: the API starts even if Redis is briefly unavailable.
    return ArqJobQueue(
        ArqRedis.from_url(
            redis_url,
            retry=redis_retry(),
            retry_on_error=REDIS_RETRY_ON,
            health_check_interval=REDIS_HEALTH_CHECK_SECONDS,
        )
    )
