"""arq worker entry point: `arq app.workers.settings.WorkerSettings`."""

import dataclasses
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
from app.rag.indexing import VectorIndex, ensure_collection
from app.repositories.document_store import MongoDocumentStore
from app.services.agent import AgentRunner
from app.services.document_processing import DocumentProcessor
from app.services.queue import PROCESS_DOCUMENT_TASK, RUN_AGENT_TASK
from app.storage import create_storage
from app.workers.tasks import process_document, run_agent

_settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(_settings.log_level)
    configure_tracing(_settings)
    mongo = create_mongo(_settings, appname="copilot-worker")
    await ensure_schema(mongo.db)
    qdrant = create_qdrant(_settings)
    await ensure_collection(qdrant, _settings.embedding_dimensions)
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
    # Reconnect and retry when the cloud Redis drops a connection, instead of exiting.
    redis_settings = dataclasses.replace(
        RedisSettings.from_dsn(_settings.redis_url),
        retry=redis_retry(),
        retry_on_error=REDIS_RETRY_ON,
        retry_on_timeout=True,
        conn_retries=5,
    )
