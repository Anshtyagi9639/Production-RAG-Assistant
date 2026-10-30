"""The MongoDB Atlas client: one per process, created at startup and closed at shutdown."""

import logging
import re
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pymongo
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure, ExecutionTimeout
from pymongo.monitoring import (
    ServerHeartbeatFailedEvent,
    ServerHeartbeatListener,
    ServerHeartbeatStartedEvent,
    ServerHeartbeatSucceededEvent,
)

from app.core.config import Settings

Document = dict[str, Any]
Database = AsyncDatabase[Document]
Session = AsyncClientSession

logger = logging.getLogger(__name__)

_TLS_REASON = re.compile(r"\[SSL: ([A-Z0-9_]+)\]")
_HINTS = {
    "TLSV1_ALERT_INTERNAL_ERROR": (
        "Atlas rejected the TLS handshake: this machine's public IP is probably not on the "
        "Atlas IP Access List (Security > Network Access)."
    ),
}


class ConnectivityLogger(ServerHeartbeatListener):
    """Logs when a MongoDB node becomes unreachable and when it recovers, once per change.

    Heartbeats run every few seconds per node; logging only the transitions keeps the log
    readable while making the cause of a ServerSelectionTimeoutError visible. Nodes are
    identified by their shard label only; no host names, URIs or credentials are logged.
    """

    def __init__(self) -> None:
        self._down: set[str] = set()
        self._lock = threading.Lock()

    @staticmethod
    def _node(connection_id: tuple[str, int | None]) -> str:
        host = connection_id[0].split(".")[0]
        return "-".join(host.split("-")[-3:])

    def started(self, event: ServerHeartbeatStartedEvent) -> None:
        return None

    def succeeded(self, event: ServerHeartbeatSucceededEvent) -> None:
        node = self._node(event.connection_id)
        with self._lock:
            if node not in self._down:
                return
            self._down.discard(node)
        logger.info("mongodb_node_reachable", extra={"node": node})

    def failed(self, event: ServerHeartbeatFailedEvent) -> None:
        node = self._node(event.connection_id)
        with self._lock:
            if node in self._down:
                return
            self._down.add(node)
        match = _TLS_REASON.search(str(event.reply))
        reason = match.group(1) if match else type(event.reply).__name__
        logger.warning(
            "mongodb_node_unreachable",
            extra={"node": node, "reason": reason, "hint": _HINTS.get(reason)},
        )


def create_mongo_client(
    settings: Settings, appname: str = "copilot-api"
) -> AsyncMongoClient[Document]:
    return AsyncMongoClient(
        settings.mongodb_uri.get_secret_value(),
        # UUIDs are stored as BSON binary subtype 4 and come back as uuid.UUID.
        uuidRepresentation="standard",
        tz_aware=True,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        appname=appname,
        event_listeners=[ConnectivityLogger()],
    )


@dataclass(frozen=True)
class Mongo:
    """The client (for sessions and transactions) and the application database."""

    client: AsyncMongoClient[Document]
    db: Database
    transaction_timeout_seconds: float = 15

    async def transaction[T](self, work: Callable[[Session], Awaitable[T]]) -> T:
        """Run `work` in a multi-document transaction, retried on transient errors.

        An exception raised by `work` aborts the transaction and propagates. The whole call,
        retries included, is bounded by `transaction_timeout_seconds`: when the database is
        unreachable the driver would otherwise keep retrying for 120 s. If the bound expires
        because the database can't be reached, that connection error is raised (so the API
        answers 503), not the driver's generic timeout.
        """
        with pymongo.timeout(self.transaction_timeout_seconds):
            async with self.client.start_session() as session:
                try:
                    return await session.with_transaction(work)
                except ExecutionTimeout as exc:
                    if isinstance(exc.__cause__, ConnectionFailure):
                        raise exc.__cause__ from exc
                    raise


def create_mongo(settings: Settings, appname: str = "copilot-api") -> Mongo:
    client = create_mongo_client(settings, appname)
    return Mongo(
        client,
        client[settings.mongodb_database],
        transaction_timeout_seconds=settings.mongodb_transaction_timeout_seconds,
    )
