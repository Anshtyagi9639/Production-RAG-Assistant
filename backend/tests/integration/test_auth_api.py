import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.db.mongo import Mongo
from app.repositories.activity import ActivityRepository
from tests.conftest import TEST_JWT_SECRET
from tests.integration.api_helpers import PASSWORD, register
from tests.integration.conftest import Api

pytestmark = pytest.mark.integration


async def test_register_creates_user_workspace_owner_membership_and_activity(
    api: Api, mongo: Mongo
) -> None:
    response = await api.client.post(
        "/api/auth/register",
        json={"email": "Ana@Example.com", "password": PASSWORD, "full_name": "Ana Lopez"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "ana@example.com"
    assert body["workspace"]["name"] == "Ana's workspace"
    assert body["workspace"]["role"] == "owner"
    user = await mongo.db["users"].find_one({"email": "ana@example.com"})
    assert user is not None
    assert str(user["_id"]) == body["user"]["id"]
    assert user["password_hash"].startswith("$argon2")
    assert PASSWORD not in user["password_hash"]
    member = await mongo.db["workspace_members"].find_one({"user_id": user["_id"]})
    assert member is not None
    assert (str(member["workspace_id"]), member["role"]) == (body["workspace"]["id"], "owner")
    assert await mongo.db["activity_logs"].count_documents({"action": "workspace.created"}) == 1


async def test_register_is_atomic(api: Api, mongo: Mongo, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*_: object, **__: object) -> None:
        raise RuntimeError("activity log unavailable")

    monkeypatch.setattr(ActivityRepository, "record", fail)

    response = await api.client.post(
        "/api/auth/register",
        json={"email": "atomic@example.com", "password": PASSWORD, "full_name": "Ann"},
    )

    assert response.status_code == 500
    # The user, workspace and membership were inserted in the same transaction, then rolled back.
    assert await mongo.db["users"].count_documents({"email": "atomic@example.com"}) == 0
    assert await mongo.db["workspaces"].count_documents({}) == 0
    assert await mongo.db["workspace_members"].count_documents({}) == 0


async def test_duplicate_email_is_rejected_case_insensitively(api: Api, mongo: Mongo) -> None:
    await register(api.client, "dup@example.com")

    response = await api.client.post(
        "/api/auth/register",
        json={"email": "DUP@example.com", "password": PASSWORD, "full_name": "Other"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"
    assert await mongo.db["users"].count_documents({}) == 1
    assert await mongo.db["workspaces"].count_documents({}) == 1


@pytest.mark.parametrize(
    ("email", "password"),
    [("ana@example.com", "wrong password"), ("nobody@example.com", PASSWORD)],
)
async def test_wrong_credentials_get_the_same_401(api: Api, email: str, password: str) -> None:
    await register(api.client, "ana@example.com")

    response = await api.client.post("/api/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "invalid_credentials", "message": "Incorrect email or password."}
    }


async def test_inactive_user_cannot_log_in_or_use_a_token(api: Api, mongo: Mongo) -> None:
    account = await register(api.client, "inactive@example.com")
    await mongo.db["users"].update_one({"_id": account.user_id}, {"$set": {"is_active": False}})

    login = await api.client.post(
        "/api/auth/login", json={"email": "inactive@example.com", "password": PASSWORD}
    )
    me = await api.client.get("/api/auth/me", headers={"Authorization": f"Bearer {account.token}"})

    assert login.status_code == 401
    assert me.status_code == 401


async def test_me_returns_the_user_and_their_workspaces(api: Api) -> None:
    account = await register(api.client, "me@example.com", "Mia Chen")

    response = await api.client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {account.token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["full_name"] == "Mia Chen"
    assert body["user"]["id"] == str(account.user_id)
    assert [w["id"] for w in body["workspaces"]] == [str(account.workspace_id)]


async def test_missing_token_is_rejected_with_www_authenticate(api: Api) -> None:
    response = await api.client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def _token(**claims: object) -> str:
    now = datetime.now(UTC)
    payload = {"sub": str(uuid.uuid4()), "iat": now, "exp": now + timedelta(minutes=5)}
    payload.update(claims)
    return jwt.encode(payload, TEST_JWT_SECRET, "HS256")


async def test_bad_and_expired_tokens_are_rejected(api: Api) -> None:
    account = await register(api.client, "tok@example.com")
    now = datetime.now(UTC)
    tokens = [
        "garbage",
        _token(sub=str(account.user_id), exp=now - timedelta(seconds=1)),  # expired
        _token(),  # valid signature, unknown user
        jwt.encode(
            {"sub": str(account.user_id), "iat": now, "exp": now + timedelta(minutes=5)},
            "x" * 40,
            "HS256",
        ),
    ]

    for token in tokens:
        response = await api.client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401, token
        assert response.json()["error"]["code"] == "invalid_token"


async def test_foreign_workspace_is_not_found(api: Api) -> None:
    alice = await register(api.client, "alice@example.com", "Alice")
    bob = await register(api.client, "bob@example.com", "Bob")

    for path in ("/api/documents", "/api/activity", "/api/stats"):
        response = await api.client.get(path, headers=bob.headers(alice.workspace_id))
        assert response.status_code == 404, path
        assert response.json()["error"]["code"] == "workspace_not_found"


@pytest.mark.parametrize(
    ("value", "code"), [(None, "workspace_required"), ("nope", "invalid_workspace_id")]
)
async def test_workspace_header_is_required_and_validated(
    api: Api, value: str | None, code: str
) -> None:
    account = await register(api.client, "hdr@example.com")
    headers = {"Authorization": f"Bearer {account.token}"}
    if value is not None:
        headers["X-Workspace-Id"] = value

    response = await api.client.get("/api/documents", headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


async def test_create_workspace_makes_the_creator_owner(api: Api, mongo: Mongo) -> None:
    account = await register(api.client, "owner@example.com")
    auth = {"Authorization": f"Bearer {account.token}"}

    created = await api.client.post("/api/workspaces", json={"name": "Finance"}, headers=auth)
    listed = await api.client.get("/api/workspaces", headers=auth)

    assert created.status_code == 201
    assert created.json()["role"] == "owner"
    assert [(w["name"], w["role"]) for w in listed.json()] == [
        ("Ana's workspace", "owner"),
        ("Finance", "owner"),
    ]
    workspace_id = uuid.UUID(created.json()["id"])
    member = await mongo.db["workspace_members"].find_one({"workspace_id": workspace_id})
    assert member is not None
    assert (member["user_id"], member["role"]) == (account.user_id, "owner")


async def test_owner_adds_member_who_can_read_but_not_upload(api: Api, mongo: Mongo) -> None:
    owner = await register(api.client, "own@example.com", "Olga")
    member = await register(api.client, "mem@example.com", "Max")
    auth = {"Authorization": f"Bearer {owner.token}"}

    added = await api.client.post(
        f"/api/workspaces/{owner.workspace_id}/members",
        json={"email": "MEM@example.com"},
        headers=auth,
    )
    assert added.status_code == 201
    assert added.json()["role"] == "member"
    row = await mongo.db["workspace_members"].find_one(
        {"workspace_id": owner.workspace_id, "user_id": member.user_id}
    )
    assert row is not None
    assert row["role"] == "member"

    as_member = member.headers(owner.workspace_id)
    assert (await api.client.get("/api/documents", headers=as_member)).status_code == 200
    upload = await api.client.post(
        "/api/documents/upload", files={"file": ("a.txt", b"hello")}, headers=as_member
    )
    assert upload.status_code == 403
    assert upload.json()["error"]["code"] == "owner_required"
    again = await api.client.post(
        f"/api/workspaces/{owner.workspace_id}/members",
        json={"email": "mem@example.com"},
        headers=auth,
    )
    assert again.status_code == 409
    by_member = await api.client.post(
        f"/api/workspaces/{owner.workspace_id}/members",
        json={"email": "own@example.com"},
        headers={"Authorization": f"Bearer {member.token}"},
    )
    assert by_member.status_code == 403
    members = mongo.db["workspace_members"]
    assert await members.count_documents({"workspace_id": owner.workspace_id}) == 2


async def test_adding_an_unknown_email_is_404(api: Api) -> None:
    owner = await register(api.client, "o2@example.com")

    response = await api.client.post(
        f"/api/workspaces/{owner.workspace_id}/members",
        json={"email": "ghost@example.com"},
        headers={"Authorization": f"Bearer {owner.token}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"
