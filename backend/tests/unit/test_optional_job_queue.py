"""The API without arq installed (temporary local-dev state): it starts, and uploads are
refused with 503 instead of pretending to process."""

import sys
import uuid
from pathlib import Path

import pytest
from qdrant_client import AsyncQdrantClient

from app.core.config import Settings
from app.core.errors import AppError
from app.db.mongo import Mongo
from app.models import User
from app.rag.indexing import VectorIndex
from app.services.documents import DocumentService
from app.services.queue import ArqJobQueue, create_arq_job_queue
from app.storage.local import LocalStorage
from tests.conftest import fixture_bytes


def test_queue_is_none_when_arq_is_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    # A None entry in sys.modules makes `import arq.connections` raise ImportError.
    monkeypatch.setitem(sys.modules, "arq.connections", None)

    assert create_arq_job_queue("redis://localhost:6379/0") is None


async def test_queue_uses_arq_when_it_is_installed() -> None:
    queue = create_arq_job_queue("redis://localhost:6379/0")

    assert isinstance(queue, ArqJobQueue)
    assert queue is not None
    await queue.close()


class UnusableDatabase:
    """Fails the test if the service touches the database (collections resolve, use fails)."""

    def __getitem__(self, name: str) -> "UnusableDatabase":
        return self

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"database used: {name}")


async def test_upload_without_a_queue_is_refused_before_anything_is_stored(
    settings: Settings, qdrant: AsyncQdrantClient, tmp_path: Path
) -> None:
    service = DocumentService(
        Mongo(client=None, db=UnusableDatabase()),  # type: ignore[arg-type]
        settings,
        LocalStorage(tmp_path),
        None,
        VectorIndex(qdrant),
    )

    with pytest.raises(AppError) as exc_info:
        await service.upload(
            User(id=uuid.uuid4(), email="a@example.com", password_hash="x", full_name="A"),
            uuid.uuid4(),
            "sample.txt",
            fixture_bytes("sample.txt"),
        )

    assert (exc_info.value.status_code, exc_info.value.code) == (503, "processing_unavailable")
    assert list(tmp_path.iterdir()) == []


def test_app_main_exposes_app_lazily_for_uvicorn(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.main

    monkeypatch.setattr(app.main, "get_settings", lambda: settings)

    assert app.main.app.title == settings.app_name
    with pytest.raises(AttributeError):
        _ = app.main.not_an_attribute
