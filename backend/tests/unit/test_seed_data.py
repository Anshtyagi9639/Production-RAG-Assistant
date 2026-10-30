"""The MongoDB seed fixtures: valid, consistent, workspace-correct, secret-free, and in sync with
scripts/seed_mongodb.py (which generates them)."""

import importlib.util
import json
import re
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from bson import json_util
from bson.binary import UuidRepresentation

from app.db.mongo_schema import COLLECTIONS
from app.rag.chunking import chunk_id

BACKEND = Path(__file__).resolve().parents[2]
SEED_DIR = BACKEND / "seed_data"
_EJSON = json_util.JSONOptions(uuid_representation=UuidRepresentation.STANDARD, tz_aware=True)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "seed_mongodb", BACKEND / "scripts" / "seed_mongodb.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fixtures() -> dict[str, list[dict[str, Any]]]:
    return {
        spec.name: json_util.loads(
            (SEED_DIR / f"{spec.name}.json").read_text(encoding="utf-8"), json_options=_EJSON
        )
        for spec in COLLECTIONS
    }


def test_there_is_one_valid_json_file_per_collection() -> None:
    files = {path.stem for path in SEED_DIR.glob("*.json")}

    assert files == {spec.name for spec in COLLECTIONS}
    for path in SEED_DIR.glob("*.json"):
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), list), path.name


def test_committed_json_matches_the_seed_script(tmp_path: Path) -> None:
    _load_script().export_json(tmp_path)

    for spec in COLLECTIONS:
        generated = (tmp_path / f"{spec.name}.json").read_text(encoding="utf-8")
        assert (SEED_DIR / f"{spec.name}.json").read_text(encoding="utf-8") == generated, spec.name


def test_ids_are_uuids_and_unique(fixtures: dict[str, list[dict[str, Any]]]) -> None:
    for name, records in fixtures.items():
        ids = [record["_id"] for record in records]
        assert all(isinstance(i, uuid.UUID) for i in ids), name
        assert len(ids) == len(set(ids)), name


def test_records_satisfy_their_collection_validator(
    fixtures: dict[str, list[dict[str, Any]]],
) -> None:
    for spec in COLLECTIONS:
        schema = spec.validator()["$jsonSchema"]
        for record in fixtures[spec.name]:
            missing = set(schema["required"]) - set(record)
            assert not missing, (spec.name, missing)
            unknown = set(record) - set(schema["properties"])
            assert not unknown, (spec.name, unknown)
            for field, rule in schema["properties"].items():
                if "enum" in rule and field in record:
                    assert record[field] in rule["enum"], (spec.name, field, record[field])


def test_every_reference_resolves(fixtures: dict[str, list[dict[str, Any]]]) -> None:
    ids = {name: {r["_id"] for r in records} for name, records in fixtures.items()}
    references = {
        "workspace_members": {"workspace_id": "workspaces", "user_id": "users"},
        "documents": {"workspace_id": "workspaces", "uploaded_by_id": "users"},
        "document_chunks": {"workspace_id": "workspaces", "document_id": "documents"},
        "conversations": {"workspace_id": "workspaces", "user_id": "users"},
        "messages": {"workspace_id": "workspaces", "conversation_id": "conversations"},
        "agent_runs": {"workspace_id": "workspaces", "user_id": "users"},
        "activity_logs": {"workspace_id": "workspaces", "user_id": "users"},
    }
    for collection, fields in references.items():
        for record in fixtures[collection]:
            for field, target in fields.items():
                assert record[field] in ids[target], (collection, field)


def test_children_live_in_their_parents_workspace(
    fixtures: dict[str, list[dict[str, Any]]],
) -> None:
    document_workspace = {d["_id"]: d["workspace_id"] for d in fixtures["documents"]}
    conversation_workspace = {c["_id"]: c["workspace_id"] for c in fixtures["conversations"]}

    for chunk in fixtures["document_chunks"]:
        assert chunk["workspace_id"] == document_workspace[chunk["document_id"]]
    for message in fixtures["messages"]:
        assert message["workspace_id"] == conversation_workspace[message["conversation_id"]]


def test_every_workspace_has_an_owner_and_uploaders_are_members(
    fixtures: dict[str, list[dict[str, Any]]],
) -> None:
    members = {(m["workspace_id"], m["user_id"]): m["role"] for m in fixtures["workspace_members"]}

    for workspace in fixtures["workspaces"]:
        assert any(ws == workspace["_id"] and role == "owner" for (ws, _), role in members.items())
    for document in fixtures["documents"]:
        assert members[(document["workspace_id"], document["uploaded_by_id"])] == "owner"


def test_chunks_use_the_applications_deterministic_ids(
    fixtures: dict[str, list[dict[str, Any]]],
) -> None:
    for chunk in fixtures["document_chunks"]:
        assert chunk["_id"] == chunk_id(chunk["document_id"], chunk["chunk_index"])
    counts = {d["_id"]: d["chunk_count"] for d in fixtures["documents"]}
    for document_id, count in counts.items():
        indexes = sorted(
            c["chunk_index"] for c in fixtures["document_chunks"] if c["document_id"] == document_id
        )
        assert indexes == list(range(count))
    demo = next(d for d in fixtures["documents"] if d["filename"] == "customs-wise-demo.txt")
    assert demo["chunk_count"] >= 3


def test_fixtures_contain_no_secrets_or_password_material() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in SEED_DIR.glob("*.json"))

    assert "password" not in text.lower()
    assert "$argon2" not in text
    assert not re.search(r"mongodb(\+srv)?://|rediss?://|sk-[A-Za-z0-9]|api[_-]?key", text, re.I)
    emails = set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text))
    assert emails == {"admin@copilot.example.com", "member@copilot.example.com"}


def test_demo_content_is_labelled_as_synthetic(fixtures: dict[str, list[dict[str, Any]]]) -> None:
    first_chunk = next(
        c for c in fixtures["document_chunks"] if c["chunk_index"] == 0 and c["token_count"] > 100
    )
    assert "DEVELOPMENT / DEMO CONTENT ONLY" in first_chunk["text"]
    assert "development/demo" in fixtures["messages"][1]["content"].lower()


@pytest.mark.parametrize("email", ["admin@copilot.example.com", "member@copilot.example.com"])
def test_seed_emails_are_accepted_by_the_login_schema(email: str) -> None:
    # Reserved names such as `.local` fail EmailStr validation, which made seed accounts unusable.
    from app.schemas.auth import LoginRequest

    assert LoginRequest(email=email, password="x" * 12).email == email
