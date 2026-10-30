# BUILD.md — AI Knowledge & Operations Copilot

> **Instructions for Claude Code:** This file is your complete brief. Read it fully, then build the project phase by phase **without waiting for the user between phases**. After each phase, tick its box in the **Progress** section below and commit. If a session ends or the context is cleared, reopen this file, find the first unticked phase, and continue from there.
>
> Only stop and ask the user when you need something only they can provide: an API key, a cloud account, a URL, or a decision this file doesn't cover. When you stop, give exact steps, then continue once they answer.

---

## Progress

- [x] Phase 1 — Design (write the plan into README draft, no app code)
- [ ] Phase 2 — Foundation (repo, config, Docker skeleton, health)
- [ ] Phase 3 — Database (models, Alembic migration)
- [ ] Phase 4 — Auth & workspaces
- [ ] Phase 5 — Documents & background processing
- [ ] Phase 6 — RAG indexing & semantic search
- [x] Phase 7 — Grounded AI chat
- [ ] Phase 8 — LangGraph agent + LangSmith
- [ ] Phase 9 — Frontend
- [ ] Phase 10 — Testing hardening
- [ ] Phase 11 — Full Docker verification
- [ ] Phase 12 — CI/CD
- [ ] Phase 13 — Documentation
- [ ] Phase 14 — Security review
- [ ] Phase 15 — Production review
- [ ] Phase 16 — Deploy (guided with user)
- [ ] Phase 17 — Post-deploy verification
- [ ] Phase 18 — Portfolio review, interview prep, resume bullets

**Notes / blockers:** _(Claude Code: write short notes here, e.g. "waiting for OPENAI_API_KEY", "switched X because Y")_

- Phase 1: user approved these defaults for gaps not covered here: owners add existing users via `POST /api/workspaces/{id}/members`; only owners upload/delete documents; conversations and agent runs are private to their creator; agent runs execute in the arq worker (202 + polling); JWT 60 min, no refresh; PyJWT + argon2-cffi; statuses as VARCHAR + CHECK; chunk/point IDs are `uuid5(document_id, chunk_index)`.
- Phase 2 (NOT ticked): code, config, Dockerfile and compose written; ruff, ruff format, mypy --strict, and pytest (14 offline tests) pass; app verified under uvicorn (/docs 200, /api/health 503 with per-dependency report when services are down). Not yet run: `docker compose up --build`, the backend image build, and `pytest -m integration` against live postgres/redis/qdrant.
- Blocker for Phase 2: `docker` is not found on this machine (no install under Program Files, no Docker processes, WSL not installed), although the user reports Docker Desktop is installed and running. User deferred Docker verification to a machine with Docker; Phase 2 stays unticked until then.
- Phase 3 (NOT ticked): models for all 9 tables, async session factory + `get_db_session`, hand-written migration `0001` (constraint names wrapped in `op.f`), pagination helpers (`app/core/pagination.py`). Passing offline: ruff, format, mypy --strict, 34 tests incl. a drift test comparing `alembic upgrade head --sql` with model DDL (mutation-checked) and a check that every FK leads an index. Written but NOT run (need a live Postgres): 13 integration tests for upgrade/downgrade + live `compare_metadata` drift, constraints, ON DELETE behaviour, and `paginate()`. They use a separate `<db>_test` database.
- All 9 tables kept; none dropped. `document_chunks` duplicates chunk text from Qdrant on purpose (SQL metadata tool, Qdrant rebuild, stats).
- The backend image copies only `app/`; adding `alembic/` and migrate-before-start is Phase 11's job.
- Pins: SQLAlchemy 2.0.54 (BUILD.md says 2.0; 2.1 exists). redis-py 5.3.1 because arq 0.28 requires redis<6.
- Phase 9 (NOT ticked): frontend built (commit 7732716); lint, typecheck, build pass. Not verified through compose.
- Phases 4, 5 and the indexing/search part of 6 implemented together (NOT ticked): auth + workspaces + members, activity/stats, document upload/list/detail/delete, arq worker on Redis (job id per document dedups; malformed payloads dropped), extraction/cleaning/chunking, OpenAI embedder with batch retry/backoff, Qdrant indexing with mandatory workspace filter, `/api/search` with Redis query-embedding cache. Passing offline: ruff, format, mypy --strict, 136 tests (processor transitions and failure reasons with real extraction and qdrant-client local mode, storage path safety, upload validation, JWT). Browser check against the real API (no DB): login/register show the real 500, bad token 401 redirects. Written but NOT run: 48 integration tests (need PostgreSQL; the arq test also needs Redis). Not done here: rate limiting (Phase 7), migrate-on-start (Phase 11). Real OpenAI embeddings and a Qdrant server are unverified (no key, no server).
- Blocker for Phases 3–6 checks: no `.env` with database credentials on this machine, no Redis, no Qdrant, no OPENAI_API_KEY.
- ARCHITECTURE CHANGE (user decision, 2026-10-01): PostgreSQL + SQLAlchemy + Alembic replaced by **MongoDB Atlas** (cloud) via PyMongo async, because the user does not want any database installed or run locally (no Docker, no local PostgreSQL/MongoDB). Config: `MONGODB_URI`, `MONGODB_DATABASE` (`DATABASE_URL` and `POSTGRES_*` are no longer read). The nine tables became nine collections with `$jsonSchema` validators (ex-CHECK constraints) and unique/compound indexes, created idempotently by `ensure_schema` at API/worker startup (replaces "migrations only"). UUID `_id`s (BSON subtype 4) keep the API contract unchanged. Multi-document transactions keep registration, workspace/member creation, upload, delete and the worker's complete/fail atomic; document delete removes chunks explicitly (no FK cascades). `/api/health` reports `mongodb` via a real `ping`. Redis and Qdrant unchanged. The Phase 3 notes above describe the superseded PostgreSQL work. Verified 2026-10-01 against Atlas (MongoDB 8.0.34): ruff, format, mypy (93 files), 149 offline tests, 41 integration tests on the separate `copilot_test` database, backend + frontend running with browser register/login/dashboard/knowledge/activity. Not verified: Redis, Qdrant server, OpenAI (not configured), so upload processing, search, chat and agent are blocked; the seed script is blocked until `SEED_ADMIN_PASSWORD` / `SEED_MEMBER_PASSWORD` are set. No phase ticked because of this change.
- Cloud services verified 2026-10-01 (no Docker, nothing local): MongoDB Atlas, Upstash Redis (`rediss://`), Qdrant Cloud (API key), OpenAI `text-embedding-3-small`. Real flow passed over HTTP and in Edge at 1440×900 and 390×844: register → login → upload → arq queue → worker → extraction/chunking → embeddings → Qdrant upsert → MongoDB COMPLETED → semantic search with sources, workspace isolation, delete removes chunks and vectors. 194 backend tests pass (43 integration against the cloud services). Seed (`--index-vectors`) runs idempotently; seed accounts moved from `@copilot.local` (rejected by `EmailStr` as a special-use domain, so they could not log in) to `@copilot.example.com`.
- Phase 7 (TICKED, 2026-10-01): `LLM` interface (`OpenAIChatLLM` via langchain-openai, temperature 0, timeout/retries; `FakeLLM` in tests), grounding prompt with escaped `<context>` blocks and injection rules, empty path with no LLM call, citations checked against the passages sent, conversations/messages in MongoDB (private to their creator), follow-up rewrite from history, Redis fixed-window rate limits (`429` + `Retry-After`) on chat/search/agent, token usage per message. Done-when proven by `tests/integration/test_chat_api.py` (empty path makes zero LLM calls; sources equal the passages sent). Also verified on the real services (`pytest -m live`) and in Edge at 1440×900 and 390×844.
- Phase 8 (NOT ticked): graph from section 7 (`app/agents/`), workspace-bound tools (knowledge retrieval, document metadata), runs executed by the arq worker (`run_agent`), per-node trace written as nodes finish, `agent.run_*` activity. Offline tests cover routing, the loop limit (1 + 2 rounds), validation failure → one revision → partial, and the error path; a real run works through Upstash + worker + OpenAI + Qdrant Cloud and in the browser. Blocker: LangSmith export is wired (`LANGSMITH_*` → `app/core/tracing.py`, runs tagged with workspace and run type) but unverified, because no `LANGSMITH_API_KEY` is configured. The graph node is named `final` (LangGraph forbids a node named like the `final_answer` state key); the trace records it as `final_answer`.
- Found by the real-cloud tests and fixed: a single transient Qdrant Cloud error (idle connection dropped) permanently FAILED an upload, so Qdrant calls now retry transient errors (3 attempts, backoff, never on 4xx); the model sometimes returns the agent's `analysis` as an object, now flattened instead of failing the run; the Assistant didn't show a follow-up answer sent within 10 s of the previous one (stale `fetchQuery`); the app had no favicon (console 404). `CONTEXT_TOKEN_BUDGET` default aligned with the design (6000).
- Windows: arq's Ctrl+C handling is not verified on Windows (arq can't install loop signal handlers there); deployment targets Linux, where arq handles SIGINT/SIGTERM. Hard-stopping the worker is safe: PROCESSING documents and RUNNING agent runs are re-claimed when the job is retried.
- TEMPORARY (local dev): the API imports arq lazily (`create_arq_job_queue` in `app/services/queue.py`) so it can start where arq isn't installed. Then there is no job queue: uploads return 503 `processing_unavailable` and ARQ/Redis background processing is unavailable. arq stays in requirements.txt and the worker is unchanged. Restore the hard dependency before enabling Redis-backed processing.

---

## 1. What we are building

A multi-tenant B2B SaaS app. A team creates a workspace and uploads internal documents (PDF, DOCX, TXT, MD). The app then lets them:
- search the documents semantically,
- ask questions and get grounded answers with source citations,
- run a LangGraph agent for multi-step analysis.

Core flow: **Upload → Process → Index → Search → Ask → Retrieve → Reason → Answer → Track**

It must feel like a real internal enterprise tool, not a ChatGPT clone. A recruiter should understand it from the GitHub README in a few minutes.

This is Project 1 of a 3-project portfolio. **Never start or suggest Project 2 or 3.**

Priorities: production quality > feature count · real business value > tech showcasing · clean architecture > complexity · readable code > clever code · working deployment > unfinished features.

---

## 2. Fixed technical decisions

Do not re-debate these. If one is genuinely broken, write the reason in Notes, then change it.

| Area | Decision |
|---|---|
| Backend | Python 3.12, FastAPI, PyMongo async (`AsyncMongoClient`), Pydantic v2 + `pydantic-settings` |
| Database | MongoDB Atlas (cloud; was PostgreSQL 16 — see Notes) |
| Vectors | Qdrant, collection `knowledge_chunks`, cosine distance, payload indexes on `workspace_id` and `document_id` |
| Background jobs | `arq` worker on Redis |
| Redis | job queue · per-user rate limiting on `/chat`, `/search`, `/agent/run` · short-TTL cache for query embeddings |
| LLM | OpenAI via `langchain-openai`. `OPENAI_CHAT_MODEL` (default `gpt-4o-mini`), `OPENAI_EMBEDDING_MODEL` (default `text-embedding-3-small`, 1536 dims) |
| RAG | LangChain text splitters where useful; own small retrieval module calling Qdrant with a mandatory `workspace_id` filter |
| Agent | LangGraph `StateGraph` with typed state |
| Observability | LangSmith via env vars; structured JSON logs with request IDs |
| Auth | Email + password, argon2 hashing, short-lived JWT in `Authorization: Bearer` |
| Frontend | Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, TanStack Query |
| Tests | pytest, pytest-asyncio, httpx `AsyncClient`; frontend: ESLint, `tsc --noEmit`, `next build` |
| Lint | ruff (lint + format), mypy on `app/`; ESLint + Prettier |
| Local run | `uvicorn` + `npm run dev` against Atlas; `docker compose up --build` optional (frontend, backend, worker, redis, qdrant — no database container) |
| CI | `.github/workflows/ci.yml` |

---

## 3. Non-negotiable rules

1. **Workspace isolation.** Every tenant query filters by `workspace_id` from the user's verified membership. Every Qdrant search has a `workspace_id` filter. Tests must prove User A cannot read, search, chat over, or delete User B's documents.
2. **Secrets.** Nothing hardcoded. All config comes from env via `app/core/config.py`. Keep `.env.example` complete. `.env` is git-ignored. The frontend never sees `OPENAI_API_KEY`.
3. **No hallucination.** If no chunk passes the similarity threshold, answer "not enough information in the knowledge base" **without calling the LLM**. Every answer returns sources: document id, filename, page, chunk index, score.
4. **Layering.** routes → services → repositories → models. No database queries or business logic in routes. Pydantic schemas are separate from the stored records.
5. **Controlled schema.** All collections, validators and indexes are declared in `app/db/mongo_schema.py` and applied only by the idempotent `ensure_schema` (startup, seed, tests). (Was: Alembic migrations — see Notes.)
6. **Offline tests.** Fake LLM and fake embedder behind interfaces, so all tests and CI run without an OpenAI key. The real-API check is `scripts/smoke_openai.py`.
7. **Meaningful tests.** Assert on bodies, DB state, Qdrant payloads, and status transitions — never on the status code alone.
8. **One error shape:** `{"error": {"code": str, "message": str, "details": optional}}`. No stack traces leak to clients.
9. **Upload safety.** Check extension and magic bytes, max size (`MAX_UPLOAD_MB`, default 20), and reject empty files. Store under a UUID name. Malformed files end as `FAILED` with a readable reason.
10. **Honest UI.** No fake metrics or placeholder data. Every screen has loading, empty, and error states.
11. **No bloat.** No unused files, dependencies, debug prints, `console.log`, commented-out code, or vague TODOs.
12. **Never claim something works unless you ran the command that shows it.** If you couldn't run it, say so in Notes.
13. **Never ask the user to paste secret values into chat.** Tell them which file or dashboard to put them in.

---

## 4. Product scope (MVP only)

**Personas:** workspace owner (sets up the workspace, uploads, manages docs), team member (searches and asks questions), ops analyst (uses the agent for cross-document analysis).

**Features:**
- register/login
- workspaces with owner/member roles
- upload with async processing and live status (`UPLOADED → PROCESSING → COMPLETED / FAILED`)
- document list, detail, and delete
- semantic search
- grounded chat with sources and conversation history
- LangGraph agent with a visible step trace
- activity log
- dashboard with real usage stats (document counts by status, conversations, agent runs, tokens used)

---

## 5. Database

Tables: `users`, `workspaces`, `workspace_members`, `documents`, `document_chunks`, `conversations`, `messages`, `agent_runs`, `activity_logs`. Drop any you can justify dropping, and note why.

Requirements:
- UUID primary keys and `created_at`/`updated_at`.
- Proper FKs with deliberate `ON DELETE` behavior.
- Unique constraints: user email; `(workspace_id, user_id)` membership.
- Indexes on every FK and on the common filter/sort columns (e.g. `documents(workspace_id, status, created_at)`).
- Enum/check constraint for document status.
- Store message sources and agent traces as JSONB.

Show real SQL concepts in the code: JOINs (membership checks, dashboard stats), aggregation (counts by status, token sums), pagination, sorting, and transactions (register creates user + workspace + membership atomically; document delete).

---

## 6. RAG design

**Indexing:**
extract (pypdf keeping page numbers; python-docx; plain read for TXT/MD) → clean whitespace, drop empty pages → chunk (~800 tokens, ~120 overlap, recursive splitter; justify the values in docs) → embed in batches with retry/backoff → upsert to Qdrant.

- Point ID = chunk UUID, so re-processing overwrites instead of duplicating.
- Payload: `document_id`, `workspace_id`, `filename`, `page`, `chunk_index`, `source`, `created_at`, `text`.

**Query:**
(for chat follow-ups, rewrite the question to be standalone) → embed (Redis cache) → Qdrant search with workspace filter, optional `document_ids` filter, top-k (default 6), score threshold (configurable) → if empty, return the "not enough information" answer → build numbered context within a token budget → LLM with grounding prompt → parse `[1]`, `[2]` citations → map them to real sources.

Treat document text as **data, not instructions**. The prompt must tell the model to ignore instructions found inside documents (prompt-injection defense).

---

## 7. LangGraph agent

**State:** `request, workspace_id, classification, sub_questions, retrieved_chunks, analysis, tool_results, retrieval_rounds, validation, final_answer, sources, status, error`.

**Graph:**
```
START → classify
  ├─ simple  → retrieve → answer → END
  └─ complex → plan (decompose) → retrieve → analyze
                → need_more? ──yes (max 2 extra rounds)──→ retrieve
                → validate (every claim supported by a cited chunk?)
                     ├─ fail → revise once, else return partial answer with a clear note
                     └─ pass → final_answer → END
Any node error → error node → status FAILED → END
```

**Tools** (real ones only):
- knowledge retrieval
- document metadata tool (which documents mention X; group findings by document)

**Persistence:** each run is stored in `agent_runs` with status, per-node trace with timings, output, token usage, and error.

**LangSmith:** `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`. Tag runs with workspace_id and run type. The app must behave the same with tracing off.

---

## 8. API

| Method | Path | Notes |
|---|---|---|
| POST | /api/auth/register | creates user + default workspace + owner membership (one transaction) |
| POST | /api/auth/login | returns JWT |
| GET | /api/auth/me | |
| GET/POST | /api/workspaces | |
| POST | /api/documents/upload | 202, enqueues processing |
| GET | /api/documents | paginated, sortable, filter by status |
| GET/DELETE | /api/documents/{id} | delete removes file, chunks, Qdrant points |
| POST | /api/search | ranked chunks + snippet + score |
| POST | /api/chat | create/continue conversation, answer + sources |
| GET | /api/conversations, /api/conversations/{id} | paginated |
| POST | /api/agent/run | |
| GET | /api/agent/runs/{id} | includes step trace |
| GET | /api/activity | paginated |
| GET | /api/stats | real dashboard numbers |
| GET | /api/health | mongodb, redis, qdrant reported separately |

- Current workspace comes from the `X-Workspace-Id` header and is checked by one dependency. That dependency is the single tenant-isolation choke point.
- Use correct status codes (201, 202, 204, 400, 401, 403/404, 413, 415, 422, 429 with `Retry-After`).
- Swagger at `/docs` must work.

---

## 9. Repository structure

```
.
├── BUILD.md
├── README.md
├── .env.example
├── docker-compose.yml
├── .github/workflows/ci.yml
├── docs/  architecture.md · database.md · ai-architecture.md · deployment.md · security.md · interview-prep.md
├── scripts/  smoke_openai.py · verify_deployment.py
├── backend/
│   ├── app/
│   │   ├── api/routes/ · api/dependencies.py
│   │   ├── core/ config.py · security.py · logging.py · errors.py · rate_limit.py
│   │   ├── db/ session.py · base.py
│   │   ├── models/ · schemas/ · repositories/ · services/
│   │   ├── ai/ llm.py · embeddings.py · prompts.py · retrieval.py
│   │   ├── rag/ extraction.py · chunking.py · indexing.py · chain.py
│   │   ├── agents/ knowledge_agent.py · state.py · tools.py
│   │   ├── workers/ tasks.py · settings.py
│   │   └── main.py
│   ├── tests/ unit/ · api/ · integration/ · fixtures/
│   ├── scripts/seed_mongodb.py · seed_data/ · pyproject.toml · requirements.txt · requirements-dev.txt · Dockerfile
└── frontend/  (Next.js app, Dockerfile)
```

---

## 10. Phases and "done when" checks

Run the checks at the end of each phase. Fix failures before ticking the box. Commit with a conventional message (`feat(rag): ...`).

1. **Design.** Write a draft README with the product concept, personas, architecture Mermaid diagram, schema, RAG and agent design, and deployment plan. No app code. *Done when:* the draft exists and matches sections 4–9.
2. **Foundation.**
   - FastAPI app factory, config, JSON logging with request IDs, error handler, CORS from `ALLOWED_ORIGINS`, `/api/health`.
   - Pinned requirements; ruff/mypy/pytest config.
   - `.env.example`, `.gitignore`, `.dockerignore`.
   - Multi-stage non-root backend Dockerfile; compose file with healthchecks.
   - *Done when:* compose brings up backend + postgres + redis + qdrant, health is green, `/docs` loads, tests and lint pass.
3. **Database.**
   - Async models, session, reviewed initial migration.
   - Test DB built via `alembic upgrade head`, rollback per test.
   - Pagination helpers.
   - *Done when:* upgrade and downgrade both work; constraint and cascade tests pass.
4. **Auth & workspaces.**
   - Endpoints above, argon2, JWT, membership dependency, activity logging in services.
   - *Done when:* tests cover wrong password, duplicate email, bad/expired token, and access to a foreign workspace.
5. **Documents.**
   - Upload validation, storage interface (local volume in dev, S3-compatible option for deploy), arq worker with idempotent jobs and status transitions, extraction + chunking, list/detail/delete.
   - Fixtures: 2-page PDF, DOCX, TXT, MD, empty file, corrupted PDF, disguised .exe.
   - *Done when:* all valid types reach COMPLETED in docker and bad ones end FAILED with a reason.
6. **RAG & search.**
   - Embedder interface (OpenAI + Fake), collection bootstrap, indexing in the worker, delete removes points, retrieval with mandatory workspace filter, Redis embedding cache, `/api/search`.
   - *Done when:* offline tests pass (including a two-workspace isolation test), and real search works once the user has set `OPENAI_API_KEY` in `.env`.
7. **Chat.**
   - LLM interface (OpenAI + Fake), grounding prompt, RAG chain with the no-LLM empty path, conversations/messages with JSONB sources, history + query rewrite, Redis rate limiting, token usage logging.
   - *Done when:* tests prove the empty path never calls the LLM and sources match retrieved chunks.
8. **Agent.**
   - Graph from section 7, AgentRun persistence, endpoints, LangSmith.
   - *Done when:* offline tests cover routing, loop limit, validation failure, and the error path.
   - Also: real run works; tell the user how to see the trace in LangSmith.
9. **Frontend.**
   - Pages: Login/Register; app shell with sidebar + workspace switcher; Dashboard (real stats, recent activity); Knowledge Base (drag-drop upload, status badges polling while processing, delete confirm, search); Assistant (conversation list, chat, inline citations, sources panel with filename/page/snippet/score, distinct "not enough information" state); Agent (task input, step timeline, answer with sources, clearly labeled); Activity.
   - Engineering: typed API client using only `NEXT_PUBLIC_API_URL`; redirect to login on 401.
   - Style: professional, neutral palette with one accent, responsive, accessible, no decorative gradients or glass.
   - *Done when:* lint, typecheck, and build pass, and the full flow works in the browser via compose.
10. **Testing.**
    - Fill gaps across unit/API/integration.
    - Add one offline end-to-end integration test: register → upload → process → search → chat → agent.
    - Remove status-code-only tests; report coverage; add `scripts/smoke_openai.py`.
11. **Docker.**
    - From `docker compose down -v`, run `docker compose up --build`. Migrations run automatically before the backend starts.
    - Walk the whole flow and fix issues.
12. **CI.**
    - Backend job: service containers for postgres/redis/qdrant, ruff, mypy, alembic, pytest + coverage, no OpenAI key.
    - Frontend job: lint, typecheck, build.
    - Docker job: build both images.
    - Triggers: push and PR to main.
    - *Done when:* the same commands pass locally.
13. **Docs.**
    - README starts with `# Project Name` and a one-line description, then these sections: Problem, Solution, Key Features, Architecture, AI/RAG Architecture, LangGraph Workflow, Tech Stack, Project Structure, Database Design, API Documentation, Local Setup, Environment Variables, Docker Setup, Testing, CI/CD, Deployment, Engineering Decisions, Trade-offs, Future Improvements, Interview Talking Points.
    - `docs/architecture.md` with Mermaid diagrams: system, RAG pipeline, LangGraph workflow, document processing.
    - `docs/database.md` with tables, relations, indexes, constraints, real queries, and transactions.
    - `docs/ai-architecture.md` covering OpenAI, embeddings, Qdrant, retrieval, LangChain (and where it was deliberately not used), LangGraph, LangSmith, hallucination mitigation, and source attribution.
    - Describe only what actually exists.
14. **Security.**
    - Check for: secrets in files and git history, upload safety, path traversal, SQL injection, authorization on every route, cross-workspace access in Postgres and Qdrant, validation, verbose errors, CORS, JWT, rate limits, `pip-audit`, `npm audit`, prompt injection.
    - Fix issues, add regression tests, and write `docs/security.md` as a table of severity, location, and fix.
15. **Production review.**
    - Production settings, server worker config, timeouts/retries on OpenAI and Qdrant, DB pool size, readiness check, stateless file storage.
    - Remove dead code and unused deps.
    - Re-run all tests and the full compose flow.
16. **Deploy (guided).**
    - Target: frontend on Vercel; backend + worker on Render (or Railway/Fly.io); Neon Postgres; Upstash Redis; Qdrant Cloud free tier; S3-compatible storage (e.g. Cloudflare R2).
    - Add platform config files and a migrate-on-release command.
    - Write `docs/deployment.md` with numbered steps and every env var.
    - Then **guide the user one step at a time**, waiting for confirmations and URLs.
17. **Post-deploy.**
    - Write and run `scripts/verify_deployment.py` against the live backend. It checks: health, register, login, upload, COMPLETED, search, chat with sources, agent, and that a second user can't see the first user's doc.
    - Give the user a browser checklist and record the results in `docs/deployment.md`.
18. **Portfolio review.**
    - Review the repo as a skeptical hiring manager and apply the fixes.
    - Tick the acceptance criteria below with evidence.
    - Write `docs/interview-prep.md`: 10 technical, 10 architecture, 10 AI (RAG, embeddings, vector DBs, LangChain, LangGraph, hallucination, retrieval, evaluation), and 5 difficult questions exposing real weaknesses. Each question gets the concepts to understand and the relevant file.
    - Give 3 concise resume bullets based only on what was built, with no invented numbers.

---

## 11. Final acceptance criteria

The project is complete only when all of these are true: local app works · docker compose works · postgres + alembic work · auth works · workspace authorization works · upload + processing work · Qdrant indexing works · semantic search works · RAG works · OpenAI works · sources displayed · LangGraph agent works · LangSmith configured · Redis used meaningfully · frontend polished · backend tests pass · frontend checks pass · GitHub Actions green · no secrets committed · README + architecture + deployment docs complete · app deployed · deployment verified · repo clean · code understandable · explainable in an interview.
