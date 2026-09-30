import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActivityLog, User, Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.repositories.activity import ActivityRepository
from tests.conftest import TEST_JWT_SECRET
from tests.integration.api_helpers import PASSWORD, register
from tests.integration.conftest import Api

pytestmark = pytest.mark.integration


async def _count(session: AsyncSession, model: type, *where: object) -> int:
    return await session.scalar(select(func.count()).select_from(model).where(*where)) or 0  # type: ignore[arg-type]


async def test_register_creates_user_workspace_owner_membership_and_activity(
    api: Api, db_session: AsyncSession
) -> None:
    response = await api.client.post(
        "/api/auth/register",
        json={"email": "Ana@Example.com", "password": PASSWORD, "full_name": "Ana Lopez"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "ana@example.com"
    assert body["workspace"] == {
        "id": body["workspace"]["id"],
        "name": "Ana's workspace",
        "role": "owner",
        "created_at": body["workspace"]["created_at"],
    }
    user = await db_session.scalar(select(User).where(User.email == "ana@example.com"))
    assert user is not None
    assert user.password_hash.startswith("$argon2")
    member = await db_session.scalar(
        select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
    )
    assert member is not None
    assert (str(member.workspace_id), member.role) == (body["workspace"]["id"], WorkspaceRole.OWNER)
    assert await _count(db_session, ActivityLog, ActivityLog.action == "workspace.created") == 1


async def test_register_is_atomic(
    api: Api, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_: object, **__: object) -> None:
        raise RuntimeError("activity log unavailable")

    monkeypatch.setattr(ActivityRepository, "record", fail)

    response = await api.client.post(
        "/api/auth/register",
        json={"email": "atomic@example.com", "password": PASSWORD, "full_name": "Ann"},
    )

    assert response.status_code == 500
    assert await _count(db_session, User, User.email == "atomic@example.com") == 0
    assert await _count(db_session, Workspace) == 0


async def test_duplicate_email_is_rejected_case_insensitively(
    api: Api, db_session: AsyncSession
) -> None:
    await register(api.client, "dup@example.com")

    response = await api.client.post(
        "/api/auth/register",
        json={"email": "DUP@example.com", "password": PASSWORD, "full_name": "Other"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"
    assert await _count(db_session, User) == 1


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


async def test_me_returns_the_user_and_their_workspaces(api: Api) -> None:
    account = await register(api.client, "me@example.com", "Mia Chen")

    response = await api.client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {account.token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["full_name"] == "Mia Chen"
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

    response = await api.client.get("/api/documents", headers=bob.headers(alice.workspace_id))

    assert response.status_code == 404
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


async def test_create_workspace_makes_the_creator_owner(api: Api) -> None:
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


async def test_owner_adds_member_who_can_read_but_not_upload(api: Api) -> None:
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


async def test_adding_an_unknown_email_is_404(api: Api) -> None:
    owner = await register(api.client, "o2@example.com")

    response = await api.client.post(
        f"/api/workspaces/{owner.workspace_id}/members",
        json={"email": "ghost@example.com"},
        headers={"Authorization": f"Bearer {owner.token}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"
