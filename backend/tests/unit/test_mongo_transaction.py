"""Mongo.transaction bounds the driver's retry loop and reports an unreachable database as a
connection failure (so the API answers 503). Real transactions are covered against MongoDB
Atlas in tests/integration/."""

from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any

import pytest
from pymongo import _csot
from pymongo.errors import ExecutionTimeout, OperationFailure, ServerSelectionTimeoutError

from app.db.mongo import Mongo


def _timeout_from(cause: Exception) -> ExecutionTimeout:
    """What the driver raises when the client-side timeout ends its retry loop."""
    try:
        raise ExecutionTimeout("operation exceeded time limit", 50) from cause
    except ExecutionTimeout as exc:
        return exc


class FakeSession:
    def __init__(self, error: Exception | None) -> None:
        self.error = error
        self.timeout_seen: float | None = None

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def with_transaction(self, work: Callable[["FakeSession"], Awaitable[Any]]) -> Any:
        self.timeout_seen = _csot.get_timeout()
        if self.error is not None:
            raise self.error
        return await work(self)


class FakeClient:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def start_session(self) -> FakeSession:
        return self.session


def _mongo(session: FakeSession) -> Mongo:
    return Mongo(FakeClient(session), db=None, transaction_timeout_seconds=7)  # type: ignore[arg-type]


async def test_the_whole_transaction_runs_under_the_timeout() -> None:
    session = FakeSession(error=None)

    async def work(_: Any) -> str:
        return "done"

    assert await _mongo(session).transaction(work) == "done"
    assert session.timeout_seen == 7
    assert _csot.get_timeout() is None  # restored afterwards


async def test_an_unreachable_database_surfaces_as_the_connection_error() -> None:
    cause = ServerSelectionTimeoutError("no servers: TLS handshake failed")
    session = FakeSession(error=_timeout_from(cause))

    with pytest.raises(ServerSelectionTimeoutError) as exc_info:
        await _mongo(session).transaction(lambda _: _never())

    assert exc_info.value is cause


async def test_other_timeouts_are_not_relabelled() -> None:
    session = FakeSession(error=_timeout_from(OperationFailure("write conflict", 112)))

    with pytest.raises(ExecutionTimeout):
        await _mongo(session).transaction(lambda _: _never())


async def _never() -> None:
    raise AssertionError("work must not run")
