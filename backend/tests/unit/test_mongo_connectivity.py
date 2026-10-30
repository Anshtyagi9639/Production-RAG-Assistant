import logging

import pytest
from pymongo.errors import AutoReconnect
from pymongo.monitoring import ServerHeartbeatFailedEvent, ServerHeartbeatSucceededEvent

from app.db.mongo import ConnectivityLogger

NODE = ("ac-abc123-shard-00-01.xyz987.mongodb.net", 27017)
TLS_ERROR = AutoReconnect(
    f"SSL handshake failed: {NODE[0]}:27017: [SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert "
    "internal error (_ssl.c:1018)"
)


def _failed(error: Exception = TLS_ERROR) -> ServerHeartbeatFailedEvent:
    return ServerHeartbeatFailedEvent(0.1, error, NODE)


def _succeeded() -> ServerHeartbeatSucceededEvent:
    return ServerHeartbeatSucceededEvent(0.1, None, NODE)  # type: ignore[arg-type]


def test_unreachable_node_is_logged_once_with_reason_and_hint(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.db.mongo")
    listener = ConnectivityLogger()

    for _ in range(3):
        listener.failed(_failed())

    [record] = caplog.records
    assert record.getMessage() == "mongodb_node_unreachable"
    assert record.node == "shard-00-01"  # type: ignore[attr-defined]
    assert record.reason == "TLSV1_ALERT_INTERNAL_ERROR"  # type: ignore[attr-defined]
    assert "IP Access List" in record.hint  # type: ignore[attr-defined]
    # No host names in the log line.
    assert "mongodb.net" not in str(vars(record))


def test_recovery_is_logged_once_and_a_new_failure_is_logged_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.db.mongo")
    listener = ConnectivityLogger()

    listener.succeeded(_succeeded())  # healthy from the start: nothing to log
    listener.failed(_failed())
    listener.succeeded(_succeeded())
    listener.succeeded(_succeeded())
    listener.failed(_failed(AutoReconnect("connection reset")))

    assert [(r.getMessage(), getattr(r, "reason", None)) for r in caplog.records] == [
        ("mongodb_node_unreachable", "TLSV1_ALERT_INTERNAL_ERROR"),
        ("mongodb_node_reachable", None),
        ("mongodb_node_unreachable", "AutoReconnect"),
    ]
