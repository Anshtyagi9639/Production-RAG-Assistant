import json
import logging

import pytest
from pymongo.errors import OperationFailure

from app.core.errors import AppError
from app.core.logging import JsonFormatter, email_domain, request_id_var, timed_stage


def _record(message: str, **extra: object) -> logging.LogRecord:
    record = logging.makeLogRecord({"name": "app.test", "levelno": logging.INFO, "msg": message})
    record.levelname = "INFO"
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_log_line_is_json_with_request_id_and_extra_fields() -> None:
    token = request_id_var.set("req-123")
    try:
        line = JsonFormatter().format(_record("document_processed", document_id="doc-1"))
    finally:
        request_id_var.reset(token)

    payload = json.loads(line)
    assert payload["message"] == "document_processed"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["request_id"] == "req-123"
    assert payload["document_id"] == "doc-1"
    assert "timestamp" in payload


def test_log_line_omits_request_id_outside_a_request() -> None:
    payload = json.loads(JsonFormatter().format(_record("startup")))

    assert "request_id" not in payload


def _stage_records(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    keys = ("operation", "stage", "outcome", "error", "error_code", "email_domain")
    return [
        {"message": r.getMessage(), **{k: getattr(r, k) for k in keys if hasattr(r, k)}}
        for r in caplog.records
        if r.name == "test.stage"
    ]


def test_timed_stage_logs_completion_outcome_and_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    log = logging.getLogger("test.stage")
    caplog.set_level(logging.INFO, logger="test.stage")

    with timed_stage(log, "auth.login", "user_lookup", email_domain="example.com"):
        pass
    with pytest.raises(AppError), timed_stage(log, "auth.login", "password_verify"):
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")
    with pytest.raises(OperationFailure), timed_stage(log, "auth.login", "user_lookup"):
        raise OperationFailure("bad auth : authentication failed", code=8000)

    records = _stage_records(caplog)
    assert records == [
        {
            "message": "stage_completed",
            "operation": "auth.login",
            "stage": "user_lookup",
            "email_domain": "example.com",
        },
        {
            "message": "stage_outcome",
            "operation": "auth.login",
            "stage": "password_verify",
            "outcome": "invalid_credentials",
        },
        {
            "message": "stage_failed",
            "operation": "auth.login",
            "stage": "user_lookup",
            "error": "OperationFailure",
            "error_code": 8000,
        },
    ]
    assert all(r.duration_ms >= 0 for r in caplog.records)  # type: ignore[attr-defined]
    # The driver's message is not logged, only the error type and code.
    assert "bad auth" not in caplog.text


@pytest.mark.parametrize(
    ("email", "domain"), [("Ana.Lopez@Example.COM", "example.com"), ("no-at-sign", "invalid")]
)
def test_only_the_email_domain_is_logged(email: str, domain: str) -> None:
    assert email_domain(email) == domain
