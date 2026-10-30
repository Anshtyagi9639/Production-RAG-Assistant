import asyncio

from fastapi import FastAPI
from httpx import AsyncClient
from pymongo.errors import OperationFailure

from app.api.dependencies import get_health_service
from app.services.health import HealthCheck, HealthService


async def _ok() -> None:
    return None


async def _refused() -> None:
    raise ConnectionRefusedError("connection refused")


async def _hangs() -> None:
    await asyncio.sleep(10)


def _use_checks(app: FastAPI, **checks: HealthCheck) -> None:
    service = HealthService(checks, timeout_seconds=0.05)
    app.dependency_overrides[get_health_service] = lambda: service


async def test_health_reports_each_dependency_when_all_are_up(
    app: FastAPI, client: AsyncClient
) -> None:
    _use_checks(app, mongodb=_ok, redis=_ok, qdrant=_ok)

    response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["checks"]) == {"mongodb", "redis", "qdrant"}
    for check in body["checks"].values():
        assert check["status"] == "ok"
        assert check["error"] is None
        assert check["latency_ms"] >= 0


async def test_health_returns_503_and_names_the_failing_dependency(
    app: FastAPI, client: AsyncClient
) -> None:
    _use_checks(app, mongodb=_ok, redis=_refused, qdrant=_ok)

    response = await client.get("/api/health")

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "service_unavailable"
    checks = error["details"]["checks"]
    assert checks["redis"] == {
        "status": "unavailable",
        "latency_ms": checks["redis"]["latency_ms"],
        "error": "unreachable",
    }
    assert checks["mongodb"]["status"] == "ok"
    assert checks["qdrant"]["status"] == "ok"
    assert "connection refused" not in response.text


async def test_health_times_out_a_hanging_dependency(app: FastAPI, client: AsyncClient) -> None:
    _use_checks(app, mongodb=_ok, redis=_ok, qdrant=_hangs)

    response = await client.get("/api/health")

    assert response.status_code == 503
    qdrant = response.json()["error"]["details"]["checks"]["qdrant"]
    assert qdrant["status"] == "unavailable"
    assert qdrant["error"] == "timeout"


async def _bad_auth() -> None:
    raise OperationFailure("bad auth : authentication failed", code=8000)


async def test_health_names_a_rejected_database_credential(
    app: FastAPI, client: AsyncClient
) -> None:
    _use_checks(app, mongodb=_bad_auth, redis=_ok, qdrant=_ok)

    response = await client.get("/api/health")

    assert response.status_code == 503
    checks = response.json()["error"]["details"]["checks"]
    assert checks["mongodb"]["status"] == "unavailable"
    assert checks["mongodb"]["error"] == "authentication_failed"
    assert checks["redis"]["error"] is None
