"""Agent runs against MongoDB Atlas: API (202 + polling), worker execution, persistence,
activity and isolation. The LLM and embedder are fakes; the graph and tools are real."""

import json
import uuid

import pytest

from app.agents.knowledge_agent import ANALYZE_PROMPT, CLASSIFY_PROMPT, PLAN_PROMPT, VALIDATE_PROMPT
from app.agents.tools import AgentTools
from app.ai.llm import LLMError, LLMMessage
from app.ai.retrieval import KnowledgeRetriever, RetrievedChunk
from app.db.mongo import Mongo
from app.rag.chain import ANSWER_SYSTEM_PROMPT, INSUFFICIENT_ANSWER
from tests.fakes import RecordingJobQueue, Reply
from tests.integration.api_helpers import Account, register, run_agent_jobs, run_queued_jobs, upload
from tests.integration.conftest import Api

pytestmark = pytest.mark.integration


def complex_script(messages: list[LLMMessage]) -> Reply:
    system = messages[0].content
    if system == CLASSIFY_PROMPT:
        return json.dumps({"classification": "complex"})
    if system == PLAN_PROMPT:
        return json.dumps({"sub_questions": ["annual plans refunds", "invoices retained"]})
    if system == ANALYZE_PROMPT:
        return json.dumps(
            {"analysis": "Refunds take 30 days [1]. Invoices: ten years [2].", "missing": []}
        )
    if system == VALIDATE_PROMPT:
        return json.dumps({"supported": True, "unsupported_claims": []})
    if system == ANSWER_SYSTEM_PROMPT:
        return "Refunds take 30 days [1]."
    raise AssertionError(system[:40])


async def start(api: Api, account: Account, request: str) -> dict[str, object]:
    response = await api.client.post(
        "/api/agent/run", json={"request": request}, headers=account.headers()
    )
    assert response.status_code == 202, response.text
    body: dict[str, object] = response.json()
    return body


async def with_docs(api: Api, email: str) -> Account:
    account = await register(api.client, email)
    await upload(api, account, "refunds.md", b"Refunds for annual plans take 30 days.")
    await upload(api, account, "retention.md", b"Invoices are retained for ten years.")
    await run_queued_jobs(api)
    return account


async def test_run_is_queued_then_executed_with_trace_answer_and_sources(
    api: Api, mongo: Mongo
) -> None:
    account = await with_docs(api, "agent@example.com")
    api.llm.reply = complex_script

    created = await start(api, account, "Compare refund and invoice retention rules")

    assert created["status"] == "QUEUED"
    assert created["trace"] == []
    assert created["final_answer"] is None
    [job] = api.queue.agent_jobs
    assert (str(job.run_id), job.workspace_id) == (created["id"], account.workspace_id)

    assert await run_agent_jobs(api) == ["COMPLETED"]

    run = (
        await api.client.get(f"/api/agent/runs/{created['id']}", headers=account.headers())
    ).json()
    assert run["status"] == "COMPLETED"
    assert run["classification"] == "complex"
    assert [s["node"] for s in run["trace"]] == [
        "classify",
        "plan",
        "retrieve",
        "analyze",
        "validate",
        "final_answer",
    ]
    assert all(s["status"] == "completed" for s in run["trace"])
    assert run["trace"][2]["summary"] == "Round 1: 2 searches, 2 passages from 2 documents"
    assert run["final_answer"] == "Refunds take 30 days [1]. Invoices: ten years [2]."
    assert {s["filename"] for s in run["sources"]} == {"refunds.md", "retention.md"}
    assert run["is_partial"] is False
    assert (run["prompt_tokens"], run["completion_tokens"]) == (400, 80)
    assert run["started_at"] is not None
    assert run["finished_at"] is not None

    run_id = uuid.UUID(str(created["id"]))
    actions = [
        a["action"]
        async for a in mongo.db["activity_logs"].find({"entity_id": run_id}).sort("created_at", 1)
    ]
    assert actions == ["agent.run_started", "agent.run_completed"]
    stats = (await api.client.get("/api/stats", headers=account.headers())).json()
    assert stats["agent_runs"] == 1


async def test_agent_in_another_workspace_cannot_reach_these_documents(api: Api) -> None:
    await with_docs(api, "alice-agent@example.com")
    bob = await register(api.client, "bob-agent@example.com")

    def simple(messages: list[LLMMessage]) -> Reply:
        if messages[0].content == CLASSIFY_PROMPT:
            return json.dumps({"classification": "simple"})
        raise AssertionError("no other call expected: nothing should be retrieved")

    api.llm.reply = simple
    created = await start(api, bob, "How long do refunds for annual plans take?")
    await run_agent_jobs(api)

    run = (await api.client.get(f"/api/agent/runs/{created['id']}", headers=bob.headers())).json()
    assert run["status"] == "COMPLETED"
    assert run["final_answer"] == INSUFFICIENT_ANSWER
    assert run["sources"] == []


async def test_runs_are_private_to_their_owner_and_workspace(api: Api) -> None:
    alice = await register(api.client, "own-agent@example.com")
    bob = await register(api.client, "peek-agent@example.com")
    created = await start(api, alice, "Summarise our policies")

    own = await api.client.get(f"/api/agent/runs/{created['id']}", headers=bob.headers())
    foreign = await api.client.get(
        f"/api/agent/runs/{created['id']}", headers=bob.headers(alice.workspace_id)
    )
    missing = await api.client.get(f"/api/agent/runs/{uuid.uuid4()}", headers=alice.headers())

    assert (own.status_code, own.json()["error"]["code"]) == (404, "agent_run_not_found")
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "workspace_not_found")
    assert missing.status_code == 404


async def test_worker_failure_marks_the_run_failed_with_a_safe_reason(
    api: Api, mongo: Mongo
) -> None:
    account = await with_docs(api, "fail-agent@example.com")
    api.llm.reply = LLMError()
    created = await start(api, account, "Compare our policies")

    assert await run_agent_jobs(api) == ["FAILED"]

    run = (
        await api.client.get(f"/api/agent/runs/{created['id']}", headers=account.headers())
    ).json()
    assert run["status"] == "FAILED"
    assert run["error"] == str(LLMError())
    assert run["final_answer"] is None
    assert run["trace"][-1]["status"] == "failed"
    assert await mongo.db["activity_logs"].count_documents({"action": "agent.run_failed"}) == 1


async def test_queue_outage_is_503_and_the_run_is_failed_not_stuck(api: Api, mongo: Mongo) -> None:
    account = await register(api.client, "queue-agent@example.com")
    api.app.state.job_queue = RecordingJobQueue(error=ConnectionError("redis down"))

    response = await api.client.post(
        "/api/agent/run", json={"request": "anything"}, headers=account.headers()
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "queue_unavailable"
    run = await mongo.db["agent_runs"].find_one({})
    assert run is not None
    assert run["status"] == "FAILED"


async def test_a_finished_run_is_not_executed_again(api: Api) -> None:
    account = await with_docs(api, "twice-agent@example.com")
    api.llm.reply = complex_script
    await start(api, account, "Compare policies")
    [job] = api.queue.agent_jobs
    await run_agent_jobs(api)
    calls = len(api.llm.calls)

    api.queue.agent_jobs.append(job)  # e.g. a duplicate delivery
    assert await run_agent_jobs(api) == ["skipped"]
    assert len(api.llm.calls) == calls


async def test_document_metadata_tool_groups_by_document_within_the_workspace(
    api: Api,
) -> None:
    alice = await with_docs(api, "meta-agent@example.com")
    bob = await register(api.client, "meta-other@example.com")
    await upload(api, bob, "bob.md", b"Bob's private notes on refunds.")
    await run_queued_jobs(api)
    retriever = KnowledgeRetriever(api.embedder, api.qdrant, top_k=6, score_threshold=0.0)
    alice_chunks = await AgentTools(
        retriever, api.mongo.db, alice.workspace_id
    ).knowledge_retrieval("refunds annual plans invoices")
    bob_chunks = await AgentTools(retriever, api.mongo.db, bob.workspace_id).knowledge_retrieval(
        "refunds notes"
    )
    assert {c.filename for c in alice_chunks} == {"refunds.md", "retention.md"}
    assert {c.filename for c in bob_chunks} == {"bob.md"}

    # Even if handed a chunk from another workspace, the tool only describes its own documents.
    smuggled: list[RetrievedChunk] = [*alice_chunks, *bob_chunks]
    results = await AgentTools(retriever, api.mongo.db, alice.workspace_id).document_metadata(
        smuggled
    )

    assert {r["filename"] for r in results} == {"refunds.md", "retention.md"}
    assert all(r["passages"] == 1 for r in results)


@pytest.mark.parametrize("body", [{"request": ""}, {"request": "x" * 4001}, {}])
async def test_invalid_run_requests_are_422(api: Api, body: dict[str, object]) -> None:
    account = await register(api.client, "invalid-agent@example.com")

    response = await api.client.post("/api/agent/run", json=body, headers=account.headers())

    assert response.status_code == 422
