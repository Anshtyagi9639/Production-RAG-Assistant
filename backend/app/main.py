import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq.connections import ArqRedis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.embeddings import CachedQueryEmbedder, OpenAIEmbedder
from app.api.routes import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import REQUEST_ID_HEADER, RequestContextMiddleware, configure_logging
from app.db.qdrant import create_qdrant
from app.db.redis import create_redis
from app.db.session import create_engine, create_session_factory
from app.rag.indexing import ensure_collection
from app.services.queue import ArqJobQueue
from app.storage import create_storage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    app.state.engine = create_engine(settings)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.redis = create_redis(settings)
    app.state.qdrant = create_qdrant(settings)
    app.state.storage = create_storage(settings)
    # arq stores pickled job payloads, so it needs its own client without response decoding.
    # Connections are opened lazily: the API starts even if Redis is briefly unavailable.
    arq_redis = ArqRedis.from_url(settings.redis_url)
    app.state.job_queue = ArqJobQueue(arq_redis)
    app.state.query_embedder = CachedQueryEmbedder(
        OpenAIEmbedder(settings),
        app.state.redis,
        settings.openai_embedding_model,
        settings.query_embedding_cache_ttl_seconds,
    )
    try:
        await ensure_collection(app.state.qdrant, settings.embedding_dimensions)
    except Exception as exc:
        # The worker also bootstraps the collection; /api/health reports Qdrant separately.
        logger.warning("qdrant_collection_bootstrap_failed", extra={"error": type(exc).__name__})
    try:
        yield
    finally:
        await arq_redis.aclose()
        await app.state.qdrant.close()
        await app.state.redis.aclose()
        await app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

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
