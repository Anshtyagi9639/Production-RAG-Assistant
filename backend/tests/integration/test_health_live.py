import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app

pytestmark = pytest.mark.integration


async def test_health_is_green_against_real_services() -> None:
    app = create_app(Settings(environment="test"))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/api/health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert {name: check["status"] for name, check in body["checks"].items()} == {
        "postgres": "ok",
        "redis": "ok",
        "qdrant": "ok",
    }
