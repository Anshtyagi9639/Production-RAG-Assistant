"""arq worker entry point: `arq app.workers.settings.WorkerSettings`."""

from typing import Any, ClassVar

from arq import func
from arq.connections import RedisSettings

from app.ai.embeddings import OpenAIEmbedder
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.qdrant import create_qdrant
from app.db.session import create_engine, create_session_factory
from app.rag.indexing import VectorIndex, ensure_collection
from app.repositories.document_store import SqlDocumentStore
from app.services.document_processing import DocumentProcessor
from app.services.queue import PROCESS_DOCUMENT_TASK
from app.storage import create_storage
from app.workers.tasks import process_document

_settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(_settings.log_level)
    engine = create_engine(_settings)
    qdrant = create_qdrant(_settings)
    await ensure_collection(qdrant, _settings.embedding_dimensions)
    ctx["engine"] = engine
    ctx["qdrant"] = qdrant
    ctx["processor"] = DocumentProcessor(
        store=SqlDocumentStore(create_session_factory(engine)),
        storage=create_storage(_settings),
        embedder=OpenAIEmbedder(_settings),
        index=VectorIndex(qdrant),
        embedding_batch_size=_settings.embedding_batch_size,
        embedding_max_attempts=_settings.embedding_max_attempts,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["qdrant"].close()
    await ctx["engine"].dispose()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [
        func(
            process_document,
            name=PROCESS_DOCUMENT_TASK,
            max_tries=_settings.worker_max_tries,
            timeout=_settings.worker_job_timeout_seconds,
        )
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
