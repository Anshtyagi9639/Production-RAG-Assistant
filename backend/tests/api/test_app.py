import re

from fastapi import FastAPI
from httpx import AsyncClient

REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")


async def test_unknown_route_uses_the_error_shape_and_gets_a_request_id(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}
    assert REQUEST_ID.fullmatch(response.headers["X-Request-ID"])


async def test_valid_incoming_request_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/api/does-not-exist", headers={"X-Request-ID": "trace-abc_123"})

    assert response.headers["X-Request-ID"] == "trace-abc_123"


async def test_invalid_incoming_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/api/does-not-exist", headers={"X-Request-ID": "bad id;drop"})

    assert REQUEST_ID.fullmatch(response.headers["X-Request-ID"])


async def test_unhandled_exception_returns_500_without_leaking_details(
    app: FastAPI, client: AsyncClient
) -> None:
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    app.add_api_route("/api/boom", boom)

    response = await client.get("/api/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "An unexpected error occurred."}
    }
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text
    assert REQUEST_ID.fullmatch(response.headers["X-Request-ID"])


async def test_validation_error_lists_fields_without_echoing_input(
    app: FastAPI, client: AsyncClient
) -> None:
    async def paged(page: int) -> dict[str, int]:
        return {"page": page}

    app.add_api_route("/api/paged", paged)

    response = await client.get("/api/paged", params={"page": "secret-value"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"] == [
        {
            "loc": ["query", "page"],
            "message": error["details"][0]["message"],
            "type": "int_parsing",
        }
    ]
    assert "secret-value" not in response.text


async def test_cors_allows_configured_origin_only(client: AsyncClient) -> None:
    preflight = {"Access-Control-Request-Method": "GET"}

    allowed = await client.options(
        "/api/health", headers={"Origin": "http://localhost:3000", **preflight}
    )
    denied = await client.options(
        "/api/health", headers={"Origin": "https://evil.example", **preflight}
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers


async def test_swagger_ui_and_openapi_schema_are_served(client: AsyncClient) -> None:
    docs = await client.get("/docs")
    schema = await client.get("/openapi.json")

    assert docs.status_code == 200
    assert "swagger-ui" in docs.text
    assert "/api/health" in schema.json()["paths"]
