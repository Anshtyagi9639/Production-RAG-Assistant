import uuid
from typing import Any

from app.db.mongo import Database
from app.models.enums import DocumentStatus


class StatsRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def documents_by_status(self, workspace_id: uuid.UUID) -> dict[DocumentStatus, int]:
        counts = dict.fromkeys(DocumentStatus, 0)
        pipeline: list[dict[str, Any]] = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        async for row in await self._db["documents"].aggregate(pipeline):
            counts[DocumentStatus(row["_id"])] = row["count"]
        return counts

    async def conversation_count(self, workspace_id: uuid.UUID) -> int:
        return await self._db["conversations"].count_documents({"workspace_id": workspace_id})

    async def agent_run_count(self, workspace_id: uuid.UUID) -> int:
        return await self._db["agent_runs"].count_documents({"workspace_id": workspace_id})

    async def token_totals(self, workspace_id: uuid.UUID) -> tuple[int, int]:
        """(prompt, completion) tokens across chat messages and agent runs in the workspace."""
        prompt = completion = 0
        pipeline: list[dict[str, Any]] = [
            {"$match": {"workspace_id": workspace_id}},
            {
                "$group": {
                    "_id": None,
                    "prompt": {"$sum": "$prompt_tokens"},
                    "completion": {"$sum": "$completion_tokens"},
                }
            },
        ]
        for collection in ("messages", "agent_runs"):
            async for row in await self._db[collection].aggregate(pipeline):
                prompt += int(row["prompt"])
                completion += int(row["completion"])
        return prompt, completion
