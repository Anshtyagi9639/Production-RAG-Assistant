import uuid
from dataclasses import dataclass

from httpx import AsyncClient

from app.rag.indexing import VectorIndex
from app.repositories.document_store import SqlDocumentStore
from app.services.document_processing import DocumentProcessor, Outcome
from tests.integration.conftest import Api

PASSWORD = "correct horse battery"


@dataclass
class Account:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    token: str

    def headers(self, workspace_id: uuid.UUID | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Workspace-Id": str(workspace_id or self.workspace_id),
        }


async def register(client: AsyncClient, email: str, full_name: str = "Ana Lopez") -> Account:
    registered = await client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, "full_name": full_name}
    )
    assert registered.status_code == 201, registered.text
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    body = registered.json()
    return Account(
        user_id=uuid.UUID(body["user"]["id"]),
        workspace_id=uuid.UUID(body["workspace"]["id"]),
        token=login.json()["access_token"],
    )


async def upload(
    api: Api, account: Account, filename: str, data: bytes, workspace_id: uuid.UUID | None = None
) -> dict[str, object]:
    response = await api.client.post(
        "/api/documents/upload",
        files={"file": (filename, data)},
        headers=account.headers(workspace_id),
    )
    assert response.status_code == 202, response.text
    body: dict[str, object] = response.json()
    return body


async def run_queued_jobs(api: Api) -> list[Outcome]:
    """Process every recorded job with the real worker pipeline (PostgreSQL store, local
    storage, Qdrant client), as the arq worker would."""
    processor = DocumentProcessor(
        store=SqlDocumentStore(api.session_factory),
        storage=api.storage,
        embedder=api.embedder,
        index=VectorIndex(api.qdrant),
        embedding_batch_size=16,
        embedding_max_attempts=2,
    )
    outcomes = [await processor.process(job) for job in api.queue.jobs]
    api.queue.jobs.clear()
    return outcomes
