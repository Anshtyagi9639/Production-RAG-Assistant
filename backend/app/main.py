import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.embeddings import CachedQueryEmbedder, OpenAIEmbedder
from app.ai.llm import OpenAIChatLLM
from app.api.routes import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import REQUEST_ID_HEADER, RequestContextMiddleware, configure_logging
from app.core.tracing import configure_tracing
from app.db.mongo import create_mongo
from app.db.mongo_schema import ensure_schema
from app.db.qdrant import create_qdrant
from app.db.redis import create_redis
from app.rag.indexing import ensure_collection
from app.services.queue import create_arq_job_queue
from app.storage import create_storage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    # One MongoDB Atlas client for the whole process; connections are pooled and lazy.
    app.state.mongo = create_mongo(settings)
    app.state.redis = create_redis(settings)
    app.state.qdrant = create_qdrant(settings)
    app.state.storage = create_storage(settings)
    # None when arq is not installed (temporary local-dev state): uploads then return 503.
    job_queue = create_arq_job_queue(settings.redis_url)
    app.state.job_queue = job_queue
    app.state.query_embedder = CachedQueryEmbedder(
        OpenAIEmbedder(settings),
        app.state.redis,
        settings.openai_embedding_model,
        settings.query_embedding_cache_ttl_seconds,
    )
    app.state.llm = OpenAIChatLLM(settings)
    try:
        # Collections, validators and indexes (idempotent); replaces the Alembic migrations.
        await ensure_schema(app.state.mongo.db)
    except Exception as exc:
        # Start anyway; /api/health reports MongoDB separately and requests fail with 500/503.
        logger.warning("mongodb_schema_bootstrap_failed", extra={"error": type(exc).__name__})
    try:
        await ensure_collection(app.state.qdrant, settings.embedding_dimensions)
    except Exception as exc:
        # The worker also bootstraps the collection; /api/health reports Qdrant separately.
        logger.warning("qdrant_collection_bootstrap_failed", extra={"error": type(exc).__name__})
    try:
        yield
    finally:
        if job_queue is not None:
            await job_queue.close()
        await app.state.qdrant.close()
        await app.state.redis.aclose()
        await app.state.mongo.client.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings)

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    register_exception_handlers(app)
    # Added first so it sits inside CORS: error responses it produces still get CORS headers.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "X-Workspace-Id", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, "Retry-After"],
    )

    app.include_router(api_router, prefix="/api")
    return app


def __getattr__(name: str) -> FastAPI:
    """Supports `uvicorn app.main:app`. The app is built on first access rather than at import,
    so importing this module (e.g. in tests) doesn't require configuration."""
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
