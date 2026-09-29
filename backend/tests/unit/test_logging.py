import json
import logging

from app.core.logging import JsonFormatter, request_id_var


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
