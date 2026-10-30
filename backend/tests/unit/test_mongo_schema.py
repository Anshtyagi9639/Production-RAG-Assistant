from app.db.mongo_schema import COLLECTIONS
from app.models.enums import AgentRunStatus, DocumentStatus, MessageRole, WorkspaceRole

EXPECTED = {
    "users",
    "workspaces",
    "workspace_members",
    "documents",
    "document_chunks",
    "conversations",
    "messages",
    "agent_runs",
    "activity_logs",
}


def _spec(name: str):  # type: ignore[no-untyped-def]
    return next(spec for spec in COLLECTIONS if spec.name == name)


def test_collections_match_the_application_entities() -> None:
    names = [spec.name for spec in COLLECTIONS]

    assert set(names) == EXPECTED
    assert len(names) == len(set(names))


def test_enum_validators_use_the_applications_values() -> None:
    def enum(collection: str, field: str) -> list[str]:
        properties = _spec(collection).validator()["$jsonSchema"]["properties"]
        values: list[str] = properties[field]["enum"]
        return values

    assert enum("workspace_members", "role") == [m.value for m in WorkspaceRole]
    assert enum("documents", "status") == [m.value for m in DocumentStatus]
    assert enum("messages", "role") == [m.value for m in MessageRole]
    assert enum("agent_runs", "status") == [m.value for m in AgentRunStatus]


def test_required_fields_are_declared_and_ids_are_uuids() -> None:
    for spec in COLLECTIONS:
        schema = spec.validator()["$jsonSchema"]
        assert set(schema["required"]) <= set(schema["properties"]), spec.name
        assert schema["properties"]["_id"] == {"bsonType": "binData"}


def test_uniqueness_rules_from_the_relational_schema_are_kept() -> None:
    unique = {
        (spec.name, tuple(key for key, _ in index.document["key"].items()))
        for spec in COLLECTIONS
        for index in spec.indexes
        if index.document.get("unique")
    }

    assert unique == {
        ("users", ("email",)),
        ("workspace_members", ("workspace_id", "user_id")),
        ("documents", ("storage_key",)),
        ("document_chunks", ("document_id", "chunk_index")),
    }


def test_every_workspace_scoped_collection_is_indexed_by_workspace() -> None:
    for name in (
        "documents",
        "document_chunks",
        "conversations",
        "messages",
        "agent_runs",
        "activity_logs",
    ):
        leading = {next(iter(index.document["key"])) for index in _spec(name).indexes}
        assert "workspace_id" in leading, name


def test_index_names_are_unique() -> None:
    names = [index.document["name"] for spec in COLLECTIONS for index in spec.indexes]
    assert len(names) == len(set(names))
