"""Unique indexes and validators on the real Atlas collections (the old SQL constraints)."""

import uuid

import pytest
from pymongo.errors import DuplicateKeyError, WriteError

from app.db.mongo import Mongo
from app.db.mongo_schema import COLLECTIONS
from app.models import User, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.models.records import utcnow
from tests.integration.factories import add_document, add_user, add_workspace

pytestmark = pytest.mark.integration


async def test_every_declared_index_exists(mongo: Mongo) -> None:
    for spec in COLLECTIONS:
        existing = await mongo.db[spec.name].index_information()
        for index in spec.indexes:
            name = index.document["name"]
            assert name in existing, f"{spec.name}.{name}"
            assert existing[name].get("unique", False) == index.document.get("unique", False)


async def test_duplicate_email_is_rejected(mongo: Mongo) -> None:
    await add_user(mongo, "same@example.com")

    with pytest.raises(DuplicateKeyError):
        await add_user(mongo, "same@example.com")


async def test_uppercase_email_is_rejected_by_the_validator(mongo: Mongo) -> None:
    user = User(email="Upper@example.com", password_hash="x", full_name="U")

    with pytest.raises(WriteError):
        await mongo.db["users"].insert_one(user.to_document())


async def test_membership_is_unique_per_workspace_and_user(mongo: Mongo) -> None:
    owner = await add_user(mongo)
    workspace = await add_workspace(mongo, owner)
    again = WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role=WorkspaceRole.MEMBER)

    with pytest.raises(DuplicateKeyError):
        await mongo.db["workspace_members"].insert_one(again.to_document())


@pytest.mark.parametrize(("field", "value"), [("status", "DONE"), ("size_bytes", 0)])
async def test_invalid_document_fields_are_rejected(
    mongo: Mongo, field: str, value: object
) -> None:
    owner = await add_user(mongo)
    workspace = await add_workspace(mongo, owner)
    document = await add_document(mongo, workspace, owner)

    with pytest.raises(WriteError):
        await mongo.db["documents"].update_one({"_id": document.id}, {"$set": {field: value}})


async def test_chunk_index_is_unique_per_document(mongo: Mongo) -> None:
    owner = await add_user(mongo)
    workspace = await add_workspace(mongo, owner)
    document = await add_document(mongo, workspace, owner)
    now = utcnow()

    def chunk() -> dict[str, object]:
        return {
            "_id": uuid.uuid4(),
            "document_id": document.id,
            "workspace_id": workspace.id,
            "chunk_index": 0,
            "page": 1,
            "text": "t",
            "token_count": 1,
            "created_at": now,
            "updated_at": now,
        }

    await mongo.db["document_chunks"].insert_one(chunk())
    with pytest.raises(DuplicateKeyError):
        await mongo.db["document_chunks"].insert_one(chunk())
