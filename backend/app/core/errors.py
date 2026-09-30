from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
}


class UserFacingError(Exception):
    """A failure whose message is safe to show to users (e.g. as a document's failure reason).

    Subclasses must never put secrets, paths or provider responses in the message.
    """


class AppError(Exception):
    """An expected failure that maps to a client-facing error response."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the single error shape: {"error": {"code", "message", "details"?}}."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error}, headers=headers)


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    error = cast(AppError, exc)
    return error_response(
        error.status_code, error.code, error.message, error.details, error.headers
    )


async def _http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    error = cast(StarletteHTTPException, exc)
    code = _HTTP_ERROR_CODES.get(error.status_code, "http_error")
    message = (
        error.detail if isinstance(error.detail, str) else HTTPStatus(error.status_code).phrase
    )
    return error_response(error.status_code, code, message, headers=error.headers)


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    error = cast(RequestValidationError, exc)
    # Only location, message and type: echoing the rejected input could leak secrets (passwords).
    details = [
        {"loc": list(item["loc"]), "message": item["msg"], "type": item["type"]}
        for item in error.errors()
    ]
    return error_response(422, "validation_error", "Request validation failed.", details)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
