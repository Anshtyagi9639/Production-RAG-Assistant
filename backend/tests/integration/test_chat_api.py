"""Grounded chat against MongoDB Atlas (and the real Redis for rate limits); the LLM and the
embedder are fakes at their boundary, vectors are in qdrant-client's in-process mode."""

import uuid

import pytest

from app.ai.llm import LLMError, LLMMessage
from app.db.mongo import Mongo
from app.rag.chain import ANSWER_SYSTEM_PROMPT, INSUFFICIENT_ANSWER, REWRITE_SYSTEM_PROMPT
from tests.fakes import FakeLLM, Reply
from tests.integration.api_helpers import Account, register, run_queued_jobs, upload
from tests.integration.conftest import Api

pytestmark = pytest.mark.integration

REFUNDS = b"Refunds for annual plans take 30 days. Monthly plans are refunded within 7 days."


async def ask(
    api: Api, account: Account, message: str, conversation_id: str | None = None
) -> dict[str, object]:
    body: dict[str, object] = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = await api.client.post("/api/chat", json=body, headers=account.headers())
    assert response.status_code == 200, response.text
    result: dict[str, object] = response.json()
    return result


async def with_refunds_doc(api: Api, email: str, name: str = "Ana Lopez") -> Account:
    account = await register(api.client, email, name)
    await upload(api, account, "refunds.md", REFUNDS)
    await run_queued_jobs(api)
    return account


def answer_calls(llm: FakeLLM) -> list[list[LLMMessage]]:
    return [call for call in llm.calls if call[0].content == ANSWER_SYSTEM_PROMPT]


async def test_answer_cites_retrieved_passages_and_everything_is_persisted(
    api: Api, mongo: Mongo
) -> None:
    account = await with_refunds_doc(api, "chat@example.com")
    api.llm.reply = "Annual plans are refunded within 30 days [1]."

    body = await ask(api, account, "How long do annual plan refunds take?")

    message = body["message"]
    assert isinstance(message, dict)
    assert message["role"] == "assistant"
    assert message["content"] == "Annual plans are refunded within 30 days [1]."
    assert message["insufficient_context"] is False
    [source] = message["sources"]
    assert source["index"] == 1
    assert source["filename"] == "refunds.md"
    assert source["snippet"] == REFUNDS.decode()
    # The source is exactly the passage that was sent to the model as [1].
    [call] = answer_calls(api.llm)
    assert '<source index="1" filename="refunds.md">' in call[1].content
    assert REFUNDS.decode() in call[1].content

    conversation_id = uuid.UUID(str(body["conversation_id"]))
    conversation = await mongo.db["conversations"].find_one({"_id": conversation_id})
    assert conversation is not None
    assert conversation["user_id"] == account.user_id
    assert conversation["title"] == "How long do annual plan refunds take?"
    stored = await mongo.db["messages"].find({"conversation_id": conversation_id}).to_list()
    assert [(m["role"], m["workspace_id"]) for m in stored] == [
        ("user", account.workspace_id),
        ("assistant", account.workspace_id),
    ]
    assert (stored[1]["prompt_tokens"], stored[1]["completion_tokens"]) == (100, 20)
    actions = (
        await mongo.db["activity_logs"]
        .find({"entity_id": conversation_id}, {"action": 1, "details": 1})
        .to_list()
    )
    assert sorted(a["action"] for a in actions) == ["chat.answered", "conversation.created"]
    # Activity records what happened, never the question or the answer.
    assert "refund" not in str([a.get("details") for a in actions]).lower()

    detail = await api.client.get(
        f"/api/conversations/{conversation_id}", headers=account.headers()
    )
    assert [m["role"] for m in detail.json()["messages"]] == ["user", "assistant"]
    assert detail.json()["messages"][1]["sources"] == [source]
    listed = await api.client.get("/api/conversations", headers=account.headers())
    assert [c["id"] for c in listed.json()["items"]] == [str(conversation_id)]
    stats = (await api.client.get("/api/stats", headers=account.headers())).json()
    assert stats["conversations"] == 1
    assert stats["tokens"] == {"prompt": 100, "completion": 20, "total": 120}


async def test_nothing_relevant_returns_the_fixed_answer_without_calling_the_llm(
    api: Api, mongo: Mongo
) -> None:
    account = await register(api.client, "empty@example.com")

    body = await ask(api, account, "What is our travel policy?")

    message = body["message"]
    assert isinstance(message, dict)
    assert message["content"] == INSUFFICIENT_ANSWER
    assert message["insufficient_context"] is True
    assert message["sources"] == []
    assert api.llm.calls == []
    stored = await mongo.db["messages"].find_one({"role": "assistant"})
    assert stored is not None
    assert (stored["prompt_tokens"], stored["completion_tokens"]) == (0, 0)


async def test_citations_to_unknown_sources_are_dropped(api: Api) -> None:
    account = await with_refunds_doc(api, "cite@example.com")
    api.llm.reply = "Refunds take 30 days [1][4]. See also [2]."

    body = await ask(api, account, "How long do annual plan refunds take?")

    message = body["message"]
    assert isinstance(message, dict)
    assert message["content"] == "Refunds take 30 days [1]. See also."
    assert [s["index"] for s in message["sources"]] == [1]


async def test_follow_up_is_rewritten_with_history_and_appended_in_order(
    api: Api, mongo: Mongo
) -> None:
    account = await with_refunds_doc(api, "follow@example.com")

    def reply(messages: list[LLMMessage]) -> Reply:
        if messages[0].content == REWRITE_SYSTEM_PROMPT:
            return "How long do monthly plan refunds take?"
        return "Monthly plans are refunded within 7 days [1]."

    api.llm.reply = reply
    first = await ask(api, account, "How long do annual plan refunds take?")
    second = await ask(api, account, "And for monthly?", str(first["conversation_id"]))

    assert second["conversation_id"] == first["conversation_id"]
    rewrite = next(c for c in api.llm.calls if c[0].content == REWRITE_SYSTEM_PROMPT)
    assert "How long do annual plan refunds take?" in rewrite[1].content
    assert rewrite[1].content.endswith("Latest question: And for monthly?")
    # Retrieval and the answer use the standalone question, not "And for monthly?".
    assert answer_calls(api.llm)[-1][1].content.endswith(
        "Question: How long do monthly plan refunds take?"
    )
    detail = await api.client.get(
        f"/api/conversations/{first['conversation_id']}", headers=account.headers()
    )
    assert [m["content"] for m in detail.json()["messages"]] == [
        "How long do annual plan refunds take?",
        "Monthly plans are refunded within 7 days [1].",
        "And for monthly?",
        "Monthly plans are refunded within 7 days [1].",
    ]
    assert await mongo.db["conversations"].count_documents({}) == 1


async def test_workspace_b_never_retrieves_workspace_a_documents(api: Api) -> None:
    alice = await register(api.client, "alice-chat@example.com", "Alice")
    await upload(api, alice, "launch.md", b"Project Bluebird launches on 14 March in Oslo.")
    await run_queued_jobs(api)
    bob = await register(api.client, "bob-chat@example.com", "Bob")

    body = await ask(api, bob, "When does Project Bluebird launch in Oslo?")

    message = body["message"]
    assert isinstance(message, dict)
    assert message["insufficient_context"] is True
    assert message["sources"] == []
    # Nothing from Alice's workspace reached the model (it wasn't called at all).
    assert api.llm.calls == []
    # Alice, asking the same thing, does get her document.
    api.llm.reply = "It launches on 14 March [1]."
    own = (await ask(api, alice, "When does Project Bluebird launch in Oslo?"))["message"]
    assert isinstance(own, dict)
    assert [s["filename"] for s in own["sources"]] == ["launch.md"]


async def test_conversations_are_private_to_their_owner_and_workspace(api: Api) -> None:
    alice = await with_refunds_doc(api, "own-chat@example.com", "Alice")
    bob = await register(api.client, "other-chat@example.com", "Bob")
    conversation_id = str((await ask(api, alice, "How long do refunds take?"))["conversation_id"])

    # Another user in their own workspace.
    read = await api.client.get(f"/api/conversations/{conversation_id}", headers=bob.headers())
    cont = await api.client.post(
        "/api/chat",
        json={"message": "hi", "conversation_id": conversation_id},
        headers=bob.headers(),
    )
    listed = await api.client.get("/api/conversations", headers=bob.headers())
    # Another user pointing at Alice's workspace.
    foreign = await api.client.get(
        f"/api/conversations/{conversation_id}", headers=bob.headers(alice.workspace_id)
    )
    # A member of Alice's workspace: conversations are private to their creator.
    await api.client.post(
        f"/api/workspaces/{alice.workspace_id}/members",
        json={"email": "other-chat@example.com"},
        headers={"Authorization": f"Bearer {alice.token}"},
    )
    as_member = await api.client.get(
        f"/api/conversations/{conversation_id}", headers=bob.headers(alice.workspace_id)
    )

    assert (read.status_code, read.json()["error"]["code"]) == (404, "conversation_not_found")
    assert (cont.status_code, cont.json()["error"]["code"]) == (404, "conversation_not_found")
    assert listed.json()["items"] == []
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "workspace_not_found")
    assert (as_member.status_code, as_member.json()["error"]["code"]) == (
        404,
        "conversation_not_found",
    )


async def test_llm_failure_is_503_and_nothing_is_saved(api: Api, mongo: Mongo) -> None:
    account = await with_refunds_doc(api, "fail-chat@example.com")
    api.llm.reply = LLMError()

    response = await api.client.post(
        "/api/chat", json={"message": "How long do refunds take?"}, headers=account.headers()
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_unavailable"
    assert await mongo.db["conversations"].count_documents({}) == 0
    assert await mongo.db["messages"].count_documents({}) == 0


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"message": ""}, 422),
        ({"message": "x" * 4001}, 422),
        ({"message": "hi", "conversation_id": "nope"}, 422),
    ],
)
async def test_invalid_requests_are_rejected(
    api: Api, body: dict[str, object], status: int
) -> None:
    account = await register(api.client, "invalid-chat@example.com")

    response = await api.client.post("/api/chat", json=body, headers=account.headers())

    assert response.status_code == status
    assert response.json()["error"]["code"] == "validation_error"


async def test_chat_requires_authentication(api: Api) -> None:
    response = await api.client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 401


async def test_chat_is_rate_limited_per_user_with_retry_after(api: Api) -> None:
    api.settings.rate_limit_requests = 2
    account = await register(api.client, "limit-chat@example.com")

    statuses = []
    for _ in range(3):
        response = await api.client.post(
            "/api/chat", json={"message": "anything"}, headers=account.headers()
        )
        statuses.append(response.status_code)

    assert statuses == [200, 200, 429]
    assert response.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(response.headers["Retry-After"]) <= api.settings.rate_limit_window_seconds
