"""arq worker entry point: `arq app.workers.settings.WorkerSettings`."""

import asyncio
import dataclasses
import logging
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from arq import func
from arq.connections import RedisSettings

from app.ai.embeddings import OpenAIEmbedder
from app.ai.llm import OpenAIChatLLM
from app.ai.retrieval import KnowledgeRetriever
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.tracing import configure_tracing
from app.db.mongo import create_mongo
from app.db.mongo_schema import ensure_schema
from app.db.qdrant import create_qdrant
from app.db.redis import REDIS_RETRY_ON, redis_retry
from app.rag.chunking import token_encoding
from app.rag.indexing import VectorIndex, ensure_collection
from app.repositories.document_store import MongoDocumentStore
from app.services.agent import AgentRunner
from app.services.document_processing import DocumentProcessor
from app.services.health import WORKER_HEARTBEAT_SECONDS
from app.services.queue import PROCESS_DOCUMENT_TASK, RUN_AGENT_TASK
from app.storage import create_storage
from app.workers.tasks import process_document, run_agent

_settings = get_settings()
logger = logging.getLogger(__name__)

# Startup waits out a short outage (about two minutes in all) instead of exiting at once,
# which would leave uploads queued with nothing to process them.
STARTUP_ATTEMPTS = 8
STARTUP_MAX_DELAY_SECONDS = 30


async def _with_retries(dependency: str, step: Callable[[], Awaitable[None]]) -> None:
    for attempt in range(1, STARTUP_ATTEMPTS + 1):
        try:
            await step()
            return
        except Exception as exc:
            if attempt == STARTUP_ATTEMPTS:
                raise
            delay = min(2**attempt, STARTUP_MAX_DELAY_SECONDS)
            logger.warning(
                "worker_startup_retry",
                extra={
                    "dependency": dependency,
                    "attempt": attempt,
                    "error": type(exc).__name__,
                    "retry_in_seconds": delay,
                },
            )
            await asyncio.sleep(delay)


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(_settings.log_level)
    configure_tracing(_settings)
    mongo = create_mongo(_settings, appname="copilot-worker")
    await _with_retries("mongodb", lambda: ensure_schema(mongo.db))
    qdrant = create_qdrant(_settings)
    await _with_retries("qdrant", lambda: ensure_collection(qdrant, _settings.embedding_dimensions))
    # Load the tokenizer now (about a second, once per process) instead of during the first
    # upload; the MongoDB and Qdrant connections above are already warm.
    await asyncio.to_thread(token_encoding)
    ctx["mongo"] = mongo
    ctx["qdrant"] = qdrant
    embedder = OpenAIEmbedder(_settings)
    ctx["processor"] = DocumentProcessor(
        store=MongoDocumentStore(mongo),
        storage=create_storage(_settings),
        embedder=embedder,
        index=VectorIndex(qdrant),
        embedding_batch_size=_settings.embedding_batch_size,
        embedding_max_attempts=_settings.embedding_max_attempts,
    )
    ctx["agent_runner"] = AgentRunner(
        mongo,
        KnowledgeRetriever(
            embedder,
            qdrant,
            top_k=_settings.retrieval_top_k,
            score_threshold=_settings.retrieval_score_threshold,
        ),
        OpenAIChatLLM(_settings),
        _settings,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["qdrant"].close()
    await ctx["mongo"].client.close()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [
        func(
            process_document,
            name=PROCESS_DOCUMENT_TASK,
            max_tries=_settings.worker_max_tries,
            timeout=_settings.worker_job_timeout_seconds,
        ),
        # One retry only: a crashed run is restarted from scratch, which re-spends tokens.
        func(
            run_agent,
            name=RUN_AGENT_TASK,
            max_tries=2,
            timeout=_settings.worker_job_timeout_seconds,
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    # The API's /api/health reports the worker from this heartbeat.
    health_check_interval = WORKER_HEARTBEAT_SECONDS
    # Reconnect and retry when the cloud Redis drops a connection, instead of exiting.
    redis_settings = dataclasses.replace(
        RedisSettings.from_dsn(_settings.redis_url),
        retry=redis_retry(),
        retry_on_error=REDIS_RETRY_ON,
        retry_on_timeout=True,
        conn_retries=5,
    )
