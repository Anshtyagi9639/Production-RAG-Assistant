"""Real services end to end: MongoDB Atlas (the separate `<db>_test` database), Upstash Redis,
Qdrant Cloud and the OpenAI API. Nothing is faked except that queued jobs are executed inline
(the Redis queue + worker path is covered by tests/integration/test_arq_redis.py).

Run explicitly (it costs a few cents of OpenAI usage): pytest -m live
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchAny

from app.ai.embeddings import CachedQueryEmbedder, OpenAIEmbedder
from app.ai.llm import OpenAIChatLLM
from app.ai.retrieval import KnowledgeRetriever
from app.core.config import Settings
from app.db.mongo import Mongo, create_mongo_client
from app.db.mongo_schema import COLLECTIONS, ensure_schema
from app.db.qdrant import create_qdrant
from app.db.redis import create_redis
from app.main import create_app
from app.rag.indexing import COLLECTION, VectorIndex, ensure_collection
from app.repositories.document_store import MongoDocumentStore
from app.services.agent import AgentRunner
from app.services.document_processing import DocumentProcessor
from app.storage.local import LocalStorage
from tests.conftest import TEST_JWT_SECRET
from tests.fakes import RecordingJobQueue

pytestmark = pytest.mark.live


def live_settings() -> Settings:
    settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
    if not settings.openai_key:
        pytest.skip("OPENAI_API_KEY is not set")
    test_db = f"{settings.mongodb_database}_test"
    return settings.model_copy(update={"mongodb_database": test_db})


@dataclass
class LiveApi:
    app: FastAPI
    client: AsyncClient
    settings: Settings
    mongo: Mongo
    qdrant: AsyncQdrantClient
    queue: RecordingJobQueue
    embedder: OpenAIEmbedder
    llm: OpenAIChatLLM
    storage: LocalStorage
    workspaces: list[uuid.UUID] = field(default_factory=list)

    async def process_uploads(self) -> None:
        processor = DocumentProcessor(
            store=MongoDocumentStore(self.mongo),
            storage=self.storage,
            embedder=self.embedder,
            index=VectorIndex(self.qdrant),
            embedding_batch_size=self.settings.embedding_batch_size,
            embedding_max_attempts=self.settings.embedding_max_attempts,
        )
        for job in self.queue.jobs:
            await processor.process(job)
        self.queue.jobs.clear()

    async def run_agents(self) -> None:
        runner = AgentRunner(
            self.mongo,
            KnowledgeRetriever(
                self.embedder,
                self.qdrant,
                top_k=self.settings.retrieval_top_k,
                score_threshold=self.settings.retrieval_score_threshold,
            ),
            self.llm,
            self.settings,
        )
        for job in self.queue.agent_jobs:
            await runner.run(job)
        self.queue.agent_jobs.clear()


@pytest.fixture
async def live(tmp_path: Path) -> AsyncIterator[LiveApi]:
    settings = live_settings()
    client = create_mongo_client(settings, appname="copilot-live-tests")
    database = client[settings.mongodb_database]
    await ensure_schema(database)
    for spec in COLLECTIONS:
        await database[spec.name].delete_many({})
    qdrant = create_qdrant(settings)
    await ensure_collection(qdrant, settings.embedding_dimensions)
    redis = create_redis(settings)
    embedder = OpenAIEmbedder(settings)

    app = create_app(settings)
    harness = LiveApi(
        app=app,
        client=AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120),
        settings=settings,
        mongo=Mongo(client, database),
        qdrant=qdrant,
        queue=RecordingJobQueue(),
        embedder=embedder,
        llm=OpenAIChatLLM(settings),
        storage=LocalStorage(tmp_path / "uploads"),
    )
    app.state.mongo = harness.mongo
    app.state.redis = redis
    app.state.qdrant = qdrant
    app.state.storage = harness.storage
    app.state.job_queue = harness.queue
    app.state.query_embedder = CachedQueryEmbedder(
        embedder, redis, settings.openai_embedding_model, settings.query_embedding_cache_ttl_seconds
    )
    app.state.llm = harness.llm
    try:
        async with harness.client:
            yield harness
    finally:
        # Remove this test's vectors from the shared Qdrant Cloud collection.
        if harness.workspaces:
            await qdrant.delete(
                COLLECTION,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="workspace_id",
                                match=MatchAny(any=[str(w) for w in harness.workspaces]),
                            )
                        ]
                    )
                ),
                wait=True,
            )
        await qdrant.close()
        await redis.aclose()
        await client.close()
