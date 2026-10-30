import uuid
from typing import Any

from pymongo import ReturnDocument

from app.db.mongo import Database, Session
from app.models import AgentRun
from app.models.enums import AgentRunStatus
from app.models.records import utcnow


class AgentRunRepository:
    def __init__(self, db: Database) -> None:
        self._runs = db["agent_runs"]

    async def insert(self, run: AgentRun, session: Session) -> None:
        await self._runs.insert_one(run.to_document(), session=session)

    async def get(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, run_id: uuid.UUID
    ) -> AgentRun | None:
        """Runs are private to the user who started them, within their workspace."""
        document = await self._runs.find_one(
            {"_id": run_id, "workspace_id": workspace_id, "user_id": user_id}
        )
        return AgentRun.from_document(document) if document else None

    async def claim(self, run_id: uuid.UUID, workspace_id: uuid.UUID) -> AgentRun | None:
        """QUEUED -> RUNNING, atomically. A RUNNING run is re-claimable so a job retried after
        a worker crash restarts it (its partial trace is cleared)."""
        now = utcnow()
        document = await self._runs.find_one_and_update(
            {
                "_id": run_id,
                "workspace_id": workspace_id,
                "status": {"$in": [AgentRunStatus.QUEUED.value, AgentRunStatus.RUNNING.value]},
            },
            {
                "$set": {
                    "status": AgentRunStatus.RUNNING.value,
                    "trace": [],
                    "started_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return AgentRun.from_document(document) if document else None

    async def append_step(self, run_id: uuid.UUID, step: dict[str, Any]) -> None:
        """Written as each node finishes, so the UI can show progress while the run executes."""
        await self._runs.update_one(
            {"_id": run_id}, {"$push": {"trace": step}, "$set": {"updated_at": utcnow()}}
        )

    async def finish(
        self, run_id: uuid.UUID, fields: dict[str, Any], session: Session | None = None
    ) -> None:
        now = utcnow()
        await self._runs.update_one(
            {"_id": run_id},
            {"$set": {**fields, "finished_at": now, "updated_at": now}},
            session=session,
        )
