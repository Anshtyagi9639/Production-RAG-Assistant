"""MongoDB collections for the application data (PostgreSQL -> MongoDB Atlas migration).

Each collection keeps the field names of the previous relational model, with `_id` holding the
UUID (stored as BSON binary subtype 4, so the API keeps returning the same UUID strings).
Validators mirror the old CHECK constraints; indexes follow the application's actual queries.
`ensure_schema` is idempotent and safe to run on every startup or seed.
"""

import logging
from dataclasses import dataclass
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

from app.models.enums import AgentRunStatus, DocumentStatus, MessageRole, WorkspaceRole

logger = logging.getLogger(__name__)

_UUID: dict[str, Any] = {"bsonType": "binData"}
_DATE: dict[str, Any] = {"bsonType": "date"}
_STRING: dict[str, Any] = {"bsonType": "string"}
_INT: dict[str, Any] = {"bsonType": ["int", "long"]}
_BOOL: dict[str, Any] = {"bsonType": "bool"}
_UNAUTHORIZED = 13


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    types = schema["bsonType"]
    return {**schema, "bsonType": [*(types if isinstance(types, list) else [types]), "null"]}


def _enum(values: type[Any]) -> dict[str, Any]:
    return {"bsonType": "string", "enum": [member.value for member in values]}


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    required: tuple[str, ...]
    properties: dict[str, dict[str, Any]]
    indexes: tuple[IndexModel, ...] = ()

    def validator(self) -> dict[str, Any]:
        return {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["_id", "created_at", "updated_at", *self.required],
                "properties": {
                    "_id": _UUID,
                    "created_at": _DATE,
                    "updated_at": _DATE,
                    **self.properties,
                },
            }
        }


COLLECTIONS: tuple[CollectionSpec, ...] = (
    CollectionSpec(
        "users",
        # password_hash is always set by the application; it is not required here so that
        # accounts imported from JSON fixtures (which never contain hashes) are accepted.
        ("email", "full_name", "is_active"),
        {
            "email": {**_STRING, "pattern": "^[^A-Z]*$"},
            "password_hash": _STRING,
            "full_name": _STRING,
            "is_active": _BOOL,
        },
        (IndexModel([("email", ASCENDING)], unique=True, name="uq_users_email"),),
    ),
    CollectionSpec("workspaces", ("name",), {"name": _STRING}),
    CollectionSpec(
        "workspace_members",
        ("workspace_id", "user_id", "role"),
        {"workspace_id": _UUID, "user_id": _UUID, "role": _enum(WorkspaceRole)},
        (
            IndexModel(
                [("workspace_id", ASCENDING), ("user_id", ASCENDING)],
                unique=True,
                name="uq_workspace_members_workspace_id_user_id",
            ),
            # "Which workspaces is this user in?" (login, /auth/me, the membership check).
            IndexModel([("user_id", ASCENDING)], name="ix_workspace_members_user_id"),
        ),
    ),
    CollectionSpec(
        "documents",
        ("workspace_id", "filename", "storage_key", "content_type", "size_bytes", "status"),
        {
            "workspace_id": _UUID,
            "uploaded_by_id": _nullable(_UUID),
            "filename": _STRING,
            "storage_key": _STRING,
            "content_type": _STRING,
            "size_bytes": {**_INT, "minimum": 1},
            "status": _enum(DocumentStatus),
            "error_message": _nullable(_STRING),
            "page_count": _nullable(_INT),
            "chunk_count": _nullable(_INT),
            "processed_at": _nullable(_DATE),
        },
        (
            # Document list filtered by status, newest first.
            IndexModel(
                [("workspace_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
                name="ix_documents_workspace_id_status_created_at",
            ),
            # Document list without a status filter, newest first.
            IndexModel(
                [("workspace_id", ASCENDING), ("created_at", DESCENDING)],
                name="ix_documents_workspace_id_created_at",
            ),
            IndexModel([("storage_key", ASCENDING)], unique=True, name="uq_documents_storage_key"),
        ),
    ),
    CollectionSpec(
        "document_chunks",
        ("document_id", "workspace_id", "chunk_index", "text", "token_count"),
        {
            "document_id": _UUID,
            "workspace_id": _UUID,
            "chunk_index": {**_INT, "minimum": 0},
            "page": _nullable(_INT),
            "text": _STRING,
            "token_count": _INT,
        },
        (
            IndexModel(
                [("document_id", ASCENDING), ("chunk_index", ASCENDING)],
                unique=True,
                name="uq_document_chunks_document_id_chunk_index",
            ),
            IndexModel([("workspace_id", ASCENDING)], name="ix_document_chunks_workspace_id"),
        ),
    ),
    CollectionSpec(
        "conversations",
        ("workspace_id", "user_id", "title"),
        {"workspace_id": _UUID, "user_id": _UUID, "title": _STRING},
        (
            # A user's conversations in a workspace, most recently active first.
            IndexModel(
                [("workspace_id", ASCENDING), ("user_id", ASCENDING), ("updated_at", DESCENDING)],
                name="ix_conversations_workspace_id_user_id_updated_at",
            ),
        ),
    ),
    CollectionSpec(
        "messages",
        # workspace_id is denormalized from the conversation so token totals and tenant
        # filters don't need a lookup.
        (
            "conversation_id",
            "workspace_id",
            "role",
            "content",
            "sources",
            "insufficient_context",
            "prompt_tokens",
            "completion_tokens",
        ),
        {
            "conversation_id": _UUID,
            "workspace_id": _UUID,
            "role": _enum(MessageRole),
            "content": _STRING,
            "sources": {"bsonType": "array"},
            "insufficient_context": _BOOL,
            "prompt_tokens": _INT,
            "completion_tokens": _INT,
        },
        (
            IndexModel(
                [("conversation_id", ASCENDING), ("created_at", ASCENDING)],
                name="ix_messages_conversation_id_created_at",
            ),
            IndexModel([("workspace_id", ASCENDING)], name="ix_messages_workspace_id"),
        ),
    ),
    CollectionSpec(
        "agent_runs",
        (
            "workspace_id",
            "request",
            "status",
            "trace",
            "sources",
            "is_partial",
            "prompt_tokens",
            "completion_tokens",
        ),
        {
            "workspace_id": _UUID,
            "user_id": _nullable(_UUID),
            "request": _STRING,
            "status": _enum(AgentRunStatus),
            "classification": _nullable(_STRING),
            "trace": {"bsonType": "array"},
            "final_answer": _nullable(_STRING),
            "sources": {"bsonType": "array"},
            "is_partial": _BOOL,
            "prompt_tokens": _INT,
            "completion_tokens": _INT,
            "error": _nullable(_STRING),
            "started_at": _nullable(_DATE),
            "finished_at": _nullable(_DATE),
        },
        (
            IndexModel(
                [("workspace_id", ASCENDING), ("created_at", DESCENDING)],
                name="ix_agent_runs_workspace_id_created_at",
            ),
        ),
    ),
    CollectionSpec(
        "activity_logs",
        ("workspace_id", "action"),
        {
            "workspace_id": _UUID,
            "user_id": _nullable(_UUID),
            "action": _STRING,
            "entity_type": _nullable(_STRING),
            "entity_id": _nullable(_UUID),
            "details": {"bsonType": ["object", "null"]},
        },
        (
            IndexModel(
                [("workspace_id", ASCENDING), ("created_at", DESCENDING)],
                name="ix_activity_logs_workspace_id_created_at",
            ),
        ),
    ),
)


async def ensure_schema(database: AsyncDatabase[dict[str, Any]]) -> None:
    """Create missing collections with validators, and create indexes (both idempotent)."""
    existing = set(await database.list_collection_names())
    for spec in COLLECTIONS:
        if spec.name not in existing:
            await database.create_collection(spec.name, validator=spec.validator())
        else:
            try:
                await database.command("collMod", spec.name, validator=spec.validator())
            except OperationFailure as exc:
                # Updating a validator needs the collMod privilege (dbAdmin), which an
                # application user with only readWrite doesn't have.
                if exc.code != _UNAUTHORIZED:
                    raise
                logger.warning("validator_not_updated", extra={"collection": spec.name})
        if spec.indexes:
            await database[spec.name].create_indexes(list(spec.indexes))
