import json
import logging
import re
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import AppError, error_response

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Standard LogRecord fields, plus uvicorn's ANSI-coloured duplicate of the message.
_STANDARD_RECORD_ATTRS = set(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "color_message",
}

logger = logging.getLogger("app.request")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, including the current request ID and any `extra` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        for key, value in vars(record).items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


@contextmanager
def timed_stage(log: logging.Logger, operation: str, stage: str, **fields: Any) -> Iterator[None]:
    """Log one step of an operation with its duration (the request ID is added by the formatter).

    Expected outcomes (an AppError such as wrong credentials) are logged at INFO with their
    code; anything else at WARNING with the exception type and, for database errors, the
    server's error code. Never pass secrets, credentials or tokens in `fields`.
    """
    started = time.perf_counter()
    base = {"operation": operation, "stage": stage, **fields}
    try:
        yield
    except AppError as exc:
        log.info("stage_outcome", extra={**base, "outcome": exc.code, "duration_ms": _ms(started)})
        raise
    except Exception as exc:
        log.warning(
            "stage_failed",
            extra={
                **base,
                "error": type(exc).__name__,
                "error_code": getattr(exc, "code", None),
                "duration_ms": _ms(started),
            },
        )
        raise
    log.info("stage_completed", extra={**base, "duration_ms": _ms(started)})


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def email_domain(email: str) -> str:
    """The part of an address that is safe to log."""
    return email.rsplit("@", 1)[-1].lower() if "@" in email else "invalid"


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Route uvicorn through the JSON handler; request logging is done by the middleware below.
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    # The HTTP clients behind Qdrant and OpenAI log every request URL at INFO, which puts the
    # cloud endpoints in the logs on each call. Keep their warnings and errors only.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


class RequestContextMiddleware:
    """Assigns a request ID, logs every request, and turns unhandled exceptions into a 500."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = (
            incoming if incoming and _REQUEST_ID_PATTERN.fullmatch(incoming) else uuid4().hex
        )
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception("unhandled_error")
            if response_started:
                raise
            response = error_response(500, "internal_error", "An unexpected error occurred.")
            await response(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)
