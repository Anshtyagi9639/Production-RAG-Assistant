"""The agent's tools. Both are bound to one workspace when constructed: the model never picks
the workspace, and there is no tool that reaches outside it."""

import uuid
from typing import Any

from app.ai.retrieval import KnowledgeRetriever, RetrievedChunk
from app.db.mongo import Database


class AgentTools:
    def __init__(
        self, retriever: KnowledgeRetriever, db: Database, workspace_id: uuid.UUID
    ) -> None:
        self._retriever = retriever
        self._documents = db["documents"]
        self.workspace_id = workspace_id

    async def knowledge_retrieval(self, query: str) -> list[RetrievedChunk]:
        """Passages relevant to `query`, from this workspace only."""
        return await self._retriever.search(self.workspace_id, query)

    async def document_metadata(self, chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
        """Which documents mention the findings: passages grouped by document, with the
        document's details from MongoDB (again filtered to this workspace)."""
        groups: dict[uuid.UUID, list[RetrievedChunk]] = {}
        for chunk in chunks:
            groups.setdefault(chunk.document_id, []).append(chunk)
        if not groups:
            return []
        cursor = self._documents.find(
            {"_id": {"$in": list(groups)}, "workspace_id": self.workspace_id},
            {"filename": 1, "page_count": 1, "created_at": 1},
        )
        known = {document["_id"]: document async for document in cursor}
        results = []
        for document_id, items in groups.items():
            document = known.get(document_id)
            if document is None:
                continue  # deleted since it was indexed
            results.append(
                {
                    "document_id": str(document_id),
                    "filename": document["filename"],
                    "page_count": document.get("page_count"),
                    "passages": len(items),
                    "pages": sorted({c.page for c in items if c.page is not None}),
                    "best_score": round(max(c.score for c in items), 4),
                }
            )
        return sorted(results, key=lambda r: r["best_score"], reverse=True)
