"""Agent runs: created by the API (202, QUEUED), executed by the arq worker."""

import logging
import uuid
from typing import Any

from app.agents.knowledge_agent import GENERIC_FAILURE, KnowledgeAgent, Step
from app.agents.tools import AgentTools
from app.ai.llm import LLM
from app.ai.retrieval import KnowledgeRetriever
from app.core.config import Settings
from app.core.errors import AppError
from app.db.mongo import Mongo, Session
from app.models import AgentRun, User
from app.models.enums import AgentRunStatus
from app.repositories.activity import ActivityRepository
from app.repositories.agent_runs import AgentRunRepository
from app.schemas.chat import AgentRunOut
from app.services.queue import AgentRunJob, JobQueue

logger = logging.getLogger(__name__)

AGENT_RUN_NOT_FOUND = AppError(404, "agent_run_not_found", "Agent run not found.")
QUEUE_FAILURE = "The run could not be queued. Try again."


class AgentService:
    def __init__(self, mongo: Mongo, queue: JobQueue | None) -> None:
        self._mongo = mongo
        self._queue = queue
        self._runs = AgentRunRepository(mongo.db)
        self._activity = ActivityRepository(mongo.db)

    async def start(self, user: User, workspace_id: uuid.UUID, request: str) -> AgentRunOut:
        if self._queue is None:
            raise AppError(
                503,
                "processing_unavailable",
                "Agent runs are unavailable on this server (background job queue is not "
                "configured).",
            )
        run = AgentRun(workspace_id=workspace_id, user_id=user.id, request=request)

        async def work(session: Session) -> None:
            await self._runs.insert(run, session)
            await self._activity.record(
                workspace_id=workspace_id,
                user_id=user.id,
                action="agent.run_started",
                entity_type="agent_run",
                entity_id=run.id,
                session=session,
            )

        await self._mongo.transaction(work)
        try:
            await self._queue.enqueue_agent_run(
                AgentRunJob(run_id=run.id, workspace_id=workspace_id)
            )
        except Exception as exc:
            logger.exception("enqueue_failed", extra={"agent_run_id": str(run.id)})
            fields = {"status": AgentRunStatus.FAILED.value, "error": QUEUE_FAILURE}
            await self._runs.finish(run.id, fields)
            raise AppError(
                503, "queue_unavailable", "The job queue is unavailable. Try again later."
            ) from exc
        return AgentRunOut.build(run)

    async def get(self, user: User, workspace_id: uuid.UUID, run_id: uuid.UUID) -> AgentRunOut:
        run = await self._runs.get(workspace_id, user.id, run_id)
        if run is None:
            raise AGENT_RUN_NOT_FOUND
        return AgentRunOut.build(run)


class AgentRunner:
    """Executes a queued run in the worker and persists the outcome."""

    def __init__(
        self, mongo: Mongo, retriever: KnowledgeRetriever, llm: LLM, settings: Settings
    ) -> None:
        self._mongo = mongo
        self._retriever = retriever
        self._llm = llm
        self._settings = settings
        self._runs = AgentRunRepository(mongo.db)
        self._activity = ActivityRepository(mongo.db)

    async def run(self, job: AgentRunJob) -> str:
        run = await self._runs.claim(job.run_id, job.workspace_id)
        if run is None:
            return "skipped"  # unknown, other workspace, or already finished

        async def record(step: Step) -> None:
            await self._runs.append_step(run.id, step)

        agent = KnowledgeAgent(
            self._llm,
            AgentTools(self._retriever, self._mongo.db, run.workspace_id),
            context_token_budget=self._settings.context_token_budget,
            max_output_tokens=self._settings.llm_max_output_tokens,
            max_extra_rounds=self._settings.agent_max_extra_rounds,
            recorder=record,
        )
        try:
            state = await agent.run(run.request, run_id=run.id)
        except Exception as exc:
            # Graph-level failure (node errors are already handled inside the graph).
            logger.warning("agent_run_crashed", extra={"error": type(exc).__name__})
            state = {"status": "FAILED", "error": GENERIC_FAILURE}

        failed = state.get("status") != "COMPLETED"
        fields: dict[str, Any] = {
            "status": (AgentRunStatus.FAILED if failed else AgentRunStatus.COMPLETED).value,
            "classification": state.get("classification"),
            "final_answer": None if failed else state.get("final_answer"),
            "sources": [] if failed else state.get("sources", []),
            "is_partial": bool(state.get("is_partial")),
            "error": (state.get("error") or GENERIC_FAILURE) if failed else None,
            "prompt_tokens": state.get("prompt_tokens", 0),
            "completion_tokens": state.get("completion_tokens", 0),
        }

        async def work(session: Session) -> None:
            await self._runs.finish(run.id, fields, session)
            await self._activity.record(
                workspace_id=run.workspace_id,
                user_id=run.user_id,
                action="agent.run_failed" if failed else "agent.run_completed",
                entity_type="agent_run",
                entity_id=run.id,
                details={"classification": state.get("classification")},
                session=session,
            )

        await self._mongo.transaction(work)
        return str(fields["status"])
