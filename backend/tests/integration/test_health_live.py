import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.integration.conftest import live_settings

pytestmark = pytest.mark.integration


async def test_health_is_green_against_real_services() -> None:
    app = create_app(live_settings())

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/api/health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    checks = body["checks"]
    assert {name: checks[name]["status"] for name in ("mongodb", "redis", "qdrant")} == {
        "mongodb": "ok",
        "redis": "ok",
        "qdrant": "ok",
    }
    # Reported whether or not a worker is running here; it never turns the API's health red.
    assert set(checks) == {"mongodb", "redis", "qdrant", "worker"}
    assert checks["worker"]["status"] in {"ok", "unavailable"}
