# Vercel Deployment Readiness — Knowledge Copilot

Audit date: 2026-11-02. Plan targeted: **Vercel Hobby (free)**.
Nothing has been deployed. Every result below says whether it was actually run.

---

## 1. Executive summary

**Final status: NOT READY for production.** The repository is close: it is **READY WITH LIMITATIONS** on the code side. The blockers are infrastructure decisions and accounts that only you can set up.

| Area | Verdict |
|---|---|
| Next.js frontend on Vercel | Ready. It builds, lints and typechecks, and calls the API same-origin with no hardcoded production URLs. |
| FastAPI backend as a Vercel Service | Ready with limitations. Services is in Beta. Requests are capped at 4.5 MB and 300 s. Cold starts bootstrap the schema. |
| 50 MB uploads | **Fixed in code.** Browsers now upload straight to S3 with a presigned POST, so files never pass through a Vercel Function. Not yet tested against a real bucket, because none is configured. |
| ARQ worker | Must run on a persistent host. It cannot run in a Vercel Function. |
| MongoDB Atlas from Vercel | **Blocker.** Hobby has no static outbound IPs. The only free way for Vercel Functions to reach Atlas is a `0.0.0.0/0` access-list entry. |
| Commercial use | **Blocker if commercial.** Hobby is for personal, non-commercial use only. |
| Cloud tests (Atlas, Redis, Qdrant, OpenAI) | **Not run.** Atlas currently rejects this machine's IP (`160.30.217.177`, TLS alert). |

**The smallest change that makes this deployable:** choose one of the Atlas networking options in [§8](#8-mongodb-atlas-networking-requirements), host the worker ([§10](#10-external-worker-deployment-instructions)), create the S3 bucket ([§9](#9-s3-upload-architecture-for-50-mb-files)), then follow [§14](#14-step-by-step-deployment-instructions).

---

## 2. Repository architecture and verified entry points

| Component | Location | Verified facts |
|---|---|---|
| Frontend | `frontend/` | Next.js 16.3.7 (App Router), React 19, Tailwind v4, TanStack Query, npm. `next build` passes, producing 11 routes; only `/knowledge/[id]` is dynamic. |
| Frontend API client | `frontend/src/lib/api/client.ts` | `NEXT_PUBLIC_API_URL` is the only frontend env var. When it is empty, requests go to the site's own origin under `/api`. |
| Backend API | `backend/app/main.py` (`create_app`) | FastAPI 0.141.1, Python ≥ 3.12. All 19 routes are under `/api/*`, confirmed from the OpenAPI schema. |
| Vercel entrypoint | `backend/main.py` | `app = create_app()`. Import confirmed. Matches `"entrypoint": "main:app"` in `vercel.json`. |
| Worker | `backend/app/workers/settings.py` | `arq app.workers.settings.WorkerSettings`. Tasks: `process_document` (3 tries, 600 s timeout) and `run_agent` (2 tries). |
| Database | `backend/app/db/mongo.py` | PyMongo async client, one per process. Pool size is now configurable. Transactions are bounded at 15 s. |
| Queue, cache, rate limits | `backend/app/db/redis.py` | Upstash over `rediss://`, with retry and backoff and a 30 s health check. |
| Vectors | `backend/app/db/qdrant.py` | Qdrant Cloud over HTTPS with an API key. Every search is filtered to one workspace. |
| File storage | `backend/app/storage/` | `local` (a directory) or `s3` (any S3-compatible bucket). |
| Containers | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` | Used for self-hosting. Vercel does not use them, except as an option for a Daemon ([§10](#10-external-worker-deployment-instructions)). |
| CI/CD | none | There is no `.github/workflows`. |

The browser holds a JWT in `localStorage` and sends `Authorization: Bearer …` plus `X-Workspace-Id`. There are no cookies and no OAuth callback URLs. The backend checks workspace membership on every tenant route; non-members get 404.

---

## 3. Vercel Hobby compatibility matrix

Sources were read on 2026-11-02:
- [Services](https://vercel.com/docs/services)
- [Pricing](https://vercel.com/pricing)
- [Function limits](https://vercel.com/docs/functions/limitations)
- [FastAPI](https://vercel.com/docs/frameworks/backend/fastapi)
- [Environment variables](https://vercel.com/docs/environment-variables)
- [Fair use](https://vercel.com/docs/limits/fair-use-guidelines)
- [Daemons](https://vercel.com/docs/daemons)

| Feature | Class | Detail |
|---|---|---|
| Next.js frontend | 1. Supported on Hobby | |
| Services (frontend and backend in one project) | 2. Supported with limitations | "Available in **Beta** on all plans." Hobby includes 1M service requests per month. |
| FastAPI as a Python function | 2. Supported with limitations | Max duration is 300 s on Hobby and can't be raised. Memory is 2 GB / 1 vCPU. The Python bundle can be up to 500 MB. Shutdown cleanup gets 500 ms. |
| Request or response body > 4.5 MB through a function | 3. Not possible on any plan | Answered with 413 `FUNCTION_PAYLOAD_TOO_LARGE`. Solved by direct-to-S3 uploads. |
| Lifespan startup (`ensure_schema`, Qdrant collection) | 2. Supported with limitations | It runs on each cold start and adds latency. The calls are idempotent. |
| Persistent ARQ worker in a function | 3. Requires another host | Functions are request-scoped. |
| Vercel Daemons (persistent container) | 5. Unverified | "Public Beta on all plans." Hobby includes 5 h of Active CPU and 420 GB-hrs of provisioned memory. Daemons run in production only, need a Dockerfile, use manual instance counts, and are not run by `vercel dev`. Per-instance memory sizing and egress IPs were not documented on the pages read. |
| Static outbound IPs | 4. Requires a paid feature | Not available on Hobby. Pro: $100 per project per month plus $0.15/GB, on top of the $20/month Pro seat. |
| Secure Compute (private networking) | 4. Paid feature | Enterprise only. |
| Commercial use | 4. Requires a paid plan | "Hobby teams are restricted to non-commercial personal use only." Payments, ads, or being paid to build or host the site all count as commercial. |
| Environment variables | 1. Supported | 64 KB total per deployment. Changes apply only to **new** deployments. |
| Python version | 5. Unverified | `requires-python >=3.12`. Confirm the runtime version in the first build log. |
| Hobby quotas | 1. Supported | 1M invocations, 4 h of Active CPU, 360 GB-hrs of memory, and 100 GB of transfer per month. |

---

## 4. Exact deployment blockers

| # | Blocker | Type | Fixed in repo? |
|---|---|---|---|
| B1 | Uploads above 4.5 MB failed through the function, and the required maximum is 50 MB. | Code | **Yes.** See [§9](#9-s3-upload-architecture-for-50-mb-files). |
| B2 | `STORAGE_BACKEND=local` on Vercel would lose files: function disks are temporary and not shared with the worker. | Code and config | **Yes, guarded.** On a Vercel production or preview deployment without `STORAGE_BACKEND=s3`, file operations answer 503 `storage_not_configured`. Sign-in and everything else keep working. |
| B3 | No S3 bucket exists. `S3_BUCKET` and the S3 keys are empty in `.env`. | Infrastructure | No. Your action. |
| B4 | Atlas cannot allow-list Vercel's outbound IPs on Hobby. | Infrastructure or plan | No. A decision for you. See [§8](#8-mongodb-atlas-networking-requirements). |
| B5 | No host for the ARQ worker. | Infrastructure | No. A decision for you. See [§10](#10-external-worker-deployment-instructions). |
| B6 | Commercial or non-commercial use is unconfirmed. | Plan or legal | No. Confirm. |
| B7 | Integration and end-to-end tests have not run against Atlas in this audit, because the IP was rejected. | Verification | No. Re-run after fixing Atlas access. |

---

## 5. Required changes and their priorities

### Done in this audit

| Priority | Change | Files |
|---|---|---|
| P0 | Direct-to-S3 uploads with a presigned POST that pins the key, Content-Type and exact byte size. A signed upload ticket and a server-side completion step verify the object. | `backend/app/storage/*.py`, `backend/app/services/documents.py`, `backend/app/services/uploads.py`, `backend/app/api/routes/documents.py`, `backend/app/schemas/documents.py`, `backend/app/core/security.py`, `backend/app/repositories/documents.py`, `frontend/src/lib/api/{client,endpoints,types}.ts` |
| P0 | S3 client forced to SigV4, with regional virtual-hosted URLs on AWS. Before this, boto3 signed `us-east-1` forms with SigV2 and gave other regions the global endpoint, which can redirect a browser POST. | `backend/app/storage/s3.py` |
| P0 | Storage guard: on Vercel production and preview deployments, local storage is replaced by a stand-in that answers 503 until `STORAGE_BACKEND=s3` is set. | `backend/app/core/config.py`, `backend/app/storage/__init__.py`, `backend/app/storage/unconfigured.py` |
| P0 | A loopback `NEXT_PUBLIC_API_URL` (for example `http://localhost:8000`) is ignored on any page not served from localhost, and a trailing `/api` is dropped. This fixes the production login error "Can't reach the server at http://localhost:8000". | `frontend/src/lib/api/url.ts`, `frontend/src/lib/api/client.ts` |
| P1 | `MONGODB_MAX_POOL_SIZE` setting. The default stays at the driver's 100; use 10 on Vercel. | `backend/app/core/config.py`, `backend/app/db/mongo.py` |
| P1 | `.env.example` documents the new settings and the S3 and Vercel requirements. | `.env.example` |
| P2 | `/favicon.ico` served (it was a 404). | `frontend/next.config.ts` |
| Tests | 17 new unit tests and 8 new integration tests (the integration tests have not run yet). | `backend/tests/unit/test_direct_upload.py`, `backend/tests/integration/test_direct_upload_api.py` |

Done in the earlier Vercel Services pass:
- `vercel.json`
- `.vercelignore`
- `backend/main.py`
- `pyproject.toml` with dynamic dependencies from `requirements.txt`
- the same-origin API client

### Still required (your action)

| Priority | Action |
|---|---|
| P0 | Choose the Atlas networking option ([§8](#8-mongodb-atlas-networking-requirements)). |
| P0 | Create the S3 bucket, IAM user and CORS rule ([§9](#9-s3-upload-architecture-for-50-mb-files)). |
| P0 | Choose and set up the worker host ([§10](#10-external-worker-deployment-instructions)). |
| P0 | Set the production environment variables ([§11](#11-environment-variable-checklist)). Use a **new** `JWT_SECRET_KEY` for production. |
| P1 | Run the integration suite once Atlas accepts your IP ([§13](#13-test-commands-and-actual-results)). |
| P2 | Optionally, add a CI workflow that runs ruff, mypy, pytest, tsc, eslint and `next build`. |

---

## 6. Final proposed `vercel.json` (unchanged, compatible)

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "frontend": { "root": "frontend/", "framework": "nextjs" },
    "backend":  { "root": "backend/",  "framework": "fastapi", "entrypoint": "main:app" }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "backend" } },
    { "source": "/(.*)",     "destination": { "service": "frontend" } }
  ]
}
```

- **Schema:** this matches the documented service keys (`root`, `framework`, `entrypoint`) and the `destination: { service }` rewrite form. In the earlier session, `vercel dev` accepted the config and started both services. Its frontend check was blocked only because your own `next dev` was already running.
- **Rewrites:** the first match wins. `/api/*` goes to FastAPI, which serves every route under `/api`; everything else goes to Next.js.
- **Not added:** a `daemons` entry. It waits on your worker decision; see the snippet in [§10](#10-external-worker-deployment-instructions).

If you choose Atlas option B in [§8](#8-mongodb-atlas-networking-requirements), the API moves off Vercel and `vercel.json` becomes frontend-only:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [{ "source": "/api/(.*)", "destination": "https://api.example.com/api/$1" }]
}
```

In that case, set the Vercel project's Root Directory to `frontend/`. Also set `ALLOWED_ORIGINS` on the API host if the browser ever calls it directly.

---

## 7. Required service bindings and public routing

- **Bindings: none needed.** Bindings let one service call another server-side. Here only the browser calls the API; Next.js never calls FastAPI from the server. Adding a binding would grant nothing.
- **The backend is public through the `/api/*` rewrite, and that is intended.** The browser must reach the API. Each route enforces its own auth: a Bearer JWT, a workspace-membership check, and owner-only writes.
- **A Next.js route-handler proxy was considered and rejected.** It would re-expose the same endpoints, double every function invocation against the Hobby quota, and still be bound by 4.5 MB.
- **Same origin means no CORS.** On Vercel, browser calls to `/api` need no CORS. Set `ALLOWED_ORIGINS` to your production URL anyway as defence in depth.
- **Headers.** Rewrites forward `Authorization` and `X-Workspace-Id` unchanged. No cookies are used.

---

## 8. MongoDB Atlas networking requirements

**Verified locally:** connections fail with `TLSV1_ALERT_INTERNAL_ERROR`, which is Atlas refusing an IP that isn't on its access list. Your home IP changes often: it has been 182.65.x.x, then 160.30.217.139, .223, .217, .234, .193 and now **.177**. Your laptop's IP has nothing to do with Vercel's: Vercel Functions on Hobby egress from a large, changing AWS pool.

| Option | Cost | Security | Notes |
|---|---|---|---|
| **A. `0.0.0.0/0` on the access list** | $0 | Weaker: the cluster accepts connection attempts from anywhere, protected only by TLS and the database password. | The only way for Vercel Hobby functions to reach Atlas. If you choose it: use a database user with **readWrite on the `copilot` database only** (not `atlasAdmin`) and a random password of 32+ characters, keep the seed passwords out of production, and treat it as acceptable for personal, non-sensitive data only. |
| **B. Run the API and worker on one host with a static egress IP** (recommended for real data) | Depends on the host. Verify current pricing. | Strong: Atlas allows a single IP. | Vercel serves only the frontend and rewrites `/api/*` to the API host ([§6](#6-final-proposed-verceljson-unchanged-compatible)). The worker needs Atlas access anyway, so co-locating it costs nothing extra. |
| C. Vercel Pro with Static IPs | $20/month seat plus $100/project/month plus $0.15/GB | Strong | Not Hobby. |
| D. Atlas Private Endpoint | Needs Vercel Secure Compute (Enterprise) | Strongest | Not practical here. |

**Recommendation:** B for anything holding real or sensitive documents. A only if you explicitly accept the risk for a personal demo. Option A is **not** the default.

Atlas checklist, whichever option you pick:
- [ ] A dedicated database user per environment, with the `readWrite@copilot` role.
- [ ] A connection string that uses `mongodb+srv://`. TLS is on by default; do not disable it.
- [ ] `MONGODB_MAX_POOL_SIZE=10` on Vercel. The free M0 tier allows about 500 connections, and every warm function instance opens its own pool.
- [ ] Remove old `160.30.217.x` single-IP entries you no longer need. For local development, use `160.30.217.0/24` rather than chasing each new address.

---

## 9. S3 upload architecture for 50 MB files

### Flow (implemented)

```
Browser ──1. POST /api/documents/upload/direct {filename, size_bytes}──▶ FastAPI (Vercel)
        ◀──── {url, fields, upload_token, expires_in} ─────────────────
Browser ──2. multipart POST fields + file (≤ 50 MB) ───────────────────▶ S3 (private bucket)
Browser ──3. POST /api/documents/upload/complete {upload_token}────────▶ FastAPI
                 HEAD object (size) + ranged GET of first 8 KB (type check)
                 insert document + activity (transaction) → enqueue ARQ job
        ◀──── 202 Document {status: UPLOADED} ─────────────────────────
Worker  ── reads object from S3 → extract → chunk → embed (OpenAI) → Qdrant → COMPLETED
```

| Requirement | How it's met |
|---|---|
| 1. Authenticate | Steps 1 and 3 need a valid Bearer JWT. |
| 2. Workspace permission | Both steps are **owner only**. The ticket is bound to the user and workspace; a mismatch returns 400 `invalid_upload`. |
| 3. Type and size | The extension allow-list (PDF, DOCX, TXT, MD) and `MAX_UPLOAD_MB` are checked before any URL is signed: 413, 400 or 415. |
| 4. Short-lived URL | `DIRECT_UPLOAD_EXPIRE_SECONDS` defaults to 900 s (allowed range 60–3600). |
| 5. Direct upload | The policy pins the key, the Content-Type, and `content-length-range` to exactly the declared size, so S3 rejects any other body. |
| 6. Verify the object | Missing object: 409 `upload_incomplete`. Wrong size: deleted, then 400. Wrong magic bytes: deleted, then 415. |
| 7. Record metadata | The same transaction as the existing upload path. Completing twice returns the same document (unique `storage_key`). |
| 8 and 9. Enqueue and process | Unchanged ARQ job. If the queue is down, the document is marked FAILED and the API returns 503. |
| Expired ticket | 400 `upload_expired`. The ticket outlives the URL by 5 minutes, so a just-finished upload can still be recorded. |
| Safe keys | `uuid4().hex + extension`. User filenames are never used as keys, and keys are checked against `^[0-9a-f]{32}\.(pdf\|docx\|txt\|md)$`. |
| Local development | Local storage answers 409 `direct_upload_unavailable`, and the client falls back to the multipart `/documents/upload`. |

Known gap: a user who gets a URL, uploads, and never calls `complete` leaves an orphan object, and nothing cleans these up yet. That costs storage only; it's never visible to anyone. A future cleanup job can delete objects that have no document after 24 h.

### Bucket setup (Amazon S3)

1. Create a bucket in one region, for example `ap-south-1`. Keep **Block all public access ON**. Default encryption (SSE-S3) is on for new buckets; leave it.
2. Add a CORS rule under Bucket → Permissions → CORS:

   ```json
   [
     {
       "AllowedOrigins": ["https://<your-project>.vercel.app", "http://localhost:3000"],
       "AllowedMethods": ["POST"],
       "AllowedHeaders": ["*"],
       "MaxAgeSeconds": 3000
     }
   ]
   ```

   Add your custom domain and any preview domains you use. Without this rule, the browser reports the upload as "couldn't be sent to storage".
3. Create an IAM user for the app with this policy and nothing else:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       { "Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
         "Resource": "arn:aws:s3:::<bucket>/*" },
       { "Effect": "Allow", "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::<bucket>" }
     ]
   }
   ```

   `s3:ListBucket` is required. Without it, S3 answers `403` instead of `404` for a missing object, and "upload not finished yet" would become a server error.
4. Set the following environment variables:
   - `STORAGE_BACKEND=s3`
   - `S3_BUCKET=<bucket>`
   - `S3_REGION=<region>` (not `auto`)
   - `S3_ENDPOINT_URL` left empty
   - `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`
   - `MAX_UPLOAD_MB=50`

**Cost:** S3 has no permanent free tier. Expect a few cents a month for a personal corpus of under 1 GB: storage at about $0.023/GB-month plus request fees. Check current regional pricing. Cloudflare R2 has a free tier, but **R2 does not support presigned POST**, so it would need a presigned-PUT variant, which is not implemented.

---

## 10. External worker deployment instructions

The worker is a long-running process that polls Redis. It cannot run in a Vercel Function.

**Run:** `arq app.workers.settings.WorkerSettings`, from the `backend/Dockerfile` image (the same image as the API, with the CMD overridden). The tokenizer is baked into the image.

**Needs:**
- Outbound access to Atlas, Upstash, Qdrant Cloud, OpenAI and S3.
- At least 1 GB of RAM: a 50 MB PDF is held in memory during extraction.
- These environment variables: `MONGODB_URI`, `MONGODB_DATABASE`, `REDIS_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `OPENAI_API_KEY`, `STORAGE_BACKEND=s3`, all `S3_*` variables, and `JWT_SECRET_KEY` (the settings require it even though the worker doesn't use it). Optionally `WORKER_JOB_TIMEOUT_SECONDS`, `EMBEDDING_*` and `LANGSMITH_*`.

**Behaviour verified in code and unit tests:**
- A malformed payload is dropped, not retried.
- The document processor claims each job idempotently and records COMPLETED or FAILED with a readable reason.
- Redis drops are retried with exponential backoff.
- Agent runs retry once.

Increase `WORKER_JOB_TIMEOUT_SECONDS` (default 600) if very large PDFs time out during embedding.

| Host option | Notes |
|---|---|
| A container host with a static egress IP (for example Railway, Render, Fly.io) | Recommended. Co-host the API there under Atlas option B. Free tiers, sleep policies and static-IP pricing change often: **verify before choosing.** A worker must not sleep. |
| Vercel Daemon (Beta) | Possible on Hobby within the quota, but it is production-only and Beta, its memory sizing and egress IP are unverified, and it still needs Atlas access (option A). Config sketch, not added to `vercel.json`: `"daemons": { "worker": { "root": "backend/", "entrypoint": "Dockerfile", "command": "arq app.workers.settings.WorkerSettings", "instances": { "iad1": 1 } } }`. Check the `command` key against the current Daemons reference. |
| Your own always-on machine | Free, but your laptop's changing IP is exactly the current Atlas problem. |

---

## 11. Environment variable checklist

Where to set each variable:
- **V** = Vercel project (Production and Preview), used by the backend service.
- **W** = worker host.
- **F** = frontend build.
- **L** = local only.

| Variable | Component | Purpose | Secret | Where | Required | Notes |
|---|---|---|---|---|---|---|
| `MONGODB_URI` | API, worker | Atlas connection | **Yes** | V, W | Yes | Use a production DB user. |
| `MONGODB_DATABASE` | API, worker | Database name | No | V, W | Yes | |
| `MONGODB_MAX_POOL_SIZE` | API, worker | Pool per process | No | V (10) | Recommended | **New.** |
| `REDIS_URL` | API, worker | Queue, cache, rate limits | **Yes** | V, W | Yes | `rediss://` (TLS) |
| `QDRANT_URL` / `QDRANT_API_KEY` | API, worker | Vector DB | Key: **Yes** | V, W | Yes | |
| `OPENAI_API_KEY` | API, worker | Embeddings and chat | **Yes** | V, W | Yes | Without it, uploads fail and search returns 503. |
| `JWT_SECRET_KEY` | API (worker: config only) | Signs sessions and upload tickets | **Yes** | V, W | Yes | At least 32 characters. **Generate a new one for production.** |
| `STORAGE_BACKEND` | API, worker | `s3` on Vercel | No | V, W | Yes | Enforced on Vercel. |
| `S3_BUCKET`, `S3_REGION` | API, worker | Bucket | No | V, W | Yes | Currently **empty** in `.env`. |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | API, worker | IAM user | **Yes** | V, W | Yes | Currently **empty** in `.env`. |
| `S3_ENDPOINT_URL` | API, worker | Non-AWS S3 only | No | — | No | Leave empty for AWS. |
| `MAX_UPLOAD_MB` | API | Upload limit | No | V | Yes | `50` |
| `DIRECT_UPLOAD_EXPIRE_SECONDS` | API | Presigned URL lifetime | No | V | No | **New**, default 900. |
| `ENVIRONMENT` | API, worker | `production` | No | V, W | Recommended | |
| `ALLOWED_ORIGINS` | API | CORS | No | V | Recommended | `https://<project>.vercel.app` |
| `LOG_LEVEL`, `OPENAI_*_MODEL`, `EMBEDDING_*`, `RETRIEVAL_*`, `LLM_*`, `RATE_LIMIT_*`, `WORKER_*` | API, worker | Tuning | No | V, W | No | Defaults are in `config.py`. |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | API, worker | Optional tracing | Key: **Yes** | V, W | No | |
| `VERCEL_ENV` | API | Deployment kind | No | Set by Vercel | Automatic | Used by the storage guard. |
| `NEXT_PUBLIC_API_URL` | Frontend | API base URL | No (public) | F (leave **unset** on Vercel), L | Local only | Inlined into the browser bundle. |
| `SEED_ADMIN_PASSWORD`, `SEED_MEMBER_PASSWORD` | Seed script | Dev accounts | **Yes** | L only | No | **Never set on Vercel.** |
| `POSTGRES_*`, `DATABASE_URL` | none | Leftovers in your local `.env` | — | — | No | Unused since the MongoDB migration; safe to delete locally. |

No authentication callback URLs exist: login is email and password with a JWT. Mark the secret variables as **Sensitive** in Vercel. Changes apply only to new deployments.

---

## 12. Free-tier limitations and possible costs

| Service | Free tier used | Limit to watch | Possible cost |
|---|---|---|---|
| Vercel Hobby | Frontend and API | Non-commercial only. 300 s per request. 1M invocations, 4 h of Active CPU and 100 GB of transfer per month. | Pro is $20/month if you go commercial; Static IPs add $100/project/month. |
| MongoDB Atlas M0 | Database | 512 MB storage, about 500 connections, shared CPU. | M10 and above are paid. |
| Upstash Redis | Queue | The free tier has a monthly command cap. ARQ polling uses commands continuously. Check usage in the console. | Pay-as-you-go above the cap. |
| Qdrant Cloud free cluster | Vectors | About 1 GB. Free clusters can be suspended when idle. | Paid clusters. |
| Amazon S3 | Files | No permanent free tier. | Cents per month at personal scale. |
| OpenAI | Embeddings and chat | Pay per token. Each 50 MB PDF can mean thousands of embedding calls. | Usage-based. Set a spending limit. |
| Worker host | Worker | Depends on the host. | Typically a few dollars a month for an always-on container. |

---

## 13. Test commands and actual results

Run on 2026-11-02 on Windows 11, Python 3.12 venv, Node 20.

| Check | Command | Result |
|---|---|---|
| Backend lint | `cd backend && ruff check app tests && ruff format --check app tests` | **Passed** |
| Backend types | `cd backend && mypy` (strict) | **Passed**, 78 files |
| Backend unit and API tests | `cd backend && python -m pytest -q` | **Passed**: 218 passed, 80 deselected (integration and live) |
| New direct-upload unit tests | `pytest tests/unit/test_direct_upload.py` | **Passed**, 17/17: ticket round trip, access token vs upload ticket separation, expiry, tampering, head checks, local storage, S3 policy (exact size, key, type, SigV4, regional URL), S3 HEAD/range via a botocore stubber, Vercel storage guard |
| Integration tests (Atlas) | `pytest -m integration tests/integration/test_direct_upload_api.py tests/integration/test_documents_api.py` | **Could not run.** Atlas rejected IP 160.30.217.177 (`TLSV1_ALERT_INTERNAL_ERROR`). The 8 new tests are written but **have not been executed**. |
| Live RAG tests (OpenAI and Qdrant) | `pytest -m live` | **Not run.** They need Atlas and spend credits. |
| Real S3 upload | — | **Not run.** No bucket or credentials are configured. |
| Backend entrypoint | `python -c "import main"` (from `backend/`) | **Passed.** FastAPI app, 19 paths, all under `/api`. |
| Frontend format, types, lint | `npx prettier --check src && npx tsc --noEmit && npx eslint .` | **Passed** |
| Frontend build | `npx next build` | **Passed**, 11 routes |
| Direct navigation | `curl` against the dev server for `/login`, `/register`, `/dashboard`, `/knowledge`, `/knowledge/<id>`, `/assistant`, `/agent`, `/activity`, `/favicon.ico` | **All 200.** `/` returns 307 to the app. |
| Browser upload flows (mocked API and bucket, headless Edge) | Playwright script `verify_direct_upload.mjs` (in the session's temporary scratchpad folder, not in the repo) | **Passed, 3/3.** Direct upload sends signed fields before the file and then completes. A 409 falls back to multipart. A bucket 403 shows "Storage refused the file" and never calls `complete`. |
| Dashboard browser test with the real backend | `verify_dashboard.mjs` (same scratchpad folder) | Earlier run: 47/48 checks passed; the only failure was favicon, which is now fixed and returns 200. The re-run was **blocked** by Atlas. |
| Secret scan | `git grep` for Mongo, Redis, OpenAI, AWS and JWT patterns, plus history | **Clean.** Only `<username>:<password>` placeholders. No `.env` is tracked. |
| Built bundle scan | grep `.next/static` | No secret names. `127.0.0.1:8000` appears only because the local build reads the git-ignored `frontend/.env.local`, which `.vercelignore` excludes from deploys. |
| Python bundle size | `du` of site-packages | Roughly 250–300 MB of runtime packages, measured on Windows excluding dev tools. Under the 500 MB limit; **confirm in the Vercel build log.** |
| Request size and timeouts | Code review | No API request carries a file on Vercel. Chat worst case is about 3 × 60 s LLM timeout, under 300 s. Agent runs go to the worker. |
| Vercel deployment | — | **Not performed.** |

---

## 14. Step-by-step deployment instructions

1. **Decide:** commercial or personal use ([§3](#3-vercel-hobby-compatibility-matrix)), Atlas option A or B ([§8](#8-mongodb-atlas-networking-requirements)), and the worker host ([§10](#10-external-worker-deployment-instructions)).
2. **Atlas:** create a production database user (`readWrite@copilot`) and add the access-list entry for your chosen option.
3. **S3:** create the bucket, CORS rule and IAM user ([§9](#9-s3-upload-architecture-for-50-mb-files)).
4. **Verify locally against the cloud:**
   - Add your current IP range to Atlas.
   - Run `cd backend && python -m pytest -m integration`. All tests should pass, including the 8 new direct-upload tests.
   - Optionally, set `STORAGE_BACKEND=s3` with the real bucket in `.env`, run `start-dev.ps1`, upload a PDF larger than 5 MB in the UI, and confirm it reaches **Ready**.
5. **Worker:** deploy the `backend/Dockerfile` image with the command `arq app.workers.settings.WorkerSettings` and the variables in [§11](#11-environment-variable-checklist). Check its logs for a clean startup.
6. **Vercel project:**
   - Run `npm i -g vercel`, then `vercel login`, then `vercel link` from the repository root.
   - Under option A, keep the current `vercel.json`. Under option B, use the frontend-only variant.
7. **Environment variables:** add every **V** variable from [§11](#11-environment-variable-checklist) for Production and Preview, marking the secrets Sensitive. Do **not** set `NEXT_PUBLIC_API_URL`.
8. **Preview first:** run `vercel deploy` (a preview), then work through [§15](#15-post-deployment-verification-checklist) on the preview URL. Add the preview origin to the bucket's CORS rule.
9. **Production:** once the preview passes, run `vercel deploy --prod`, then run the checklist again on the production URL.

---

## 15. Post-deployment verification checklist

- [ ] `GET https://<app>/api/health` reports MongoDB, Redis and Qdrant as `ok`.
- [ ] `/login`, `/register`, and a hard refresh on `/dashboard` and `/knowledge/<id>` all load.
- [ ] Registering a new account creates a workspace. Signing out and back in works.
- [ ] Uploading a **small TXT** goes from Uploaded to Processing to Ready.
- [ ] Uploading a **40–50 MB PDF** works. In DevTools → Network, the file goes to `*.s3.<region>.amazonaws.com`, not to `/api`, and the document reaches Ready.
- [ ] A file over 50 MB is rejected with "larger than the 50 MB limit" and no request is made to S3.
- [ ] A renamed `.exe` saved as `.pdf` is rejected with 415, and no object is left in the bucket.
- [ ] The bucket shows no public access, and its objects are encrypted (SSE-S3).
- [ ] Semantic search returns results only from the current workspace.
- [ ] An Assistant answer cites the uploaded document, and the citations open the correct passage.
- [ ] An Agent run completes, and the dashboard shows the run.
- [ ] A member (non-owner) cannot upload or delete (403).
- [ ] The worker logs show no repeated Redis reconnects or Atlas `mongodb_node_unreachable` warnings.
- [ ] Vercel → Usage shows invocations and CPU within the Hobby quota after a day of use.

---

## 16. Final status

### **NOT READY** — code is ready with limitations; infrastructure is not set up.

**Fixed in the repository (verified by unit tests, build and browser-mock tests):**
- 50 MB direct-to-S3 uploads
- S3 SigV4 and regional URL
- the Vercel storage guard
- the Mongo pool-size setting
- favicon
- `.env.example`

**Your action, before any deployment:**
1. Choose Atlas networking. A free Hobby deployment means `0.0.0.0/0`; otherwise, move the API to a host with a static IP or pay for Static IPs.
2. Create the S3 bucket, IAM user and CORS rule.
3. Host the worker.
4. Confirm the project is non-commercial, or use Pro.
5. Run the integration suite once Atlas accepts your IP.

When these are done and [§15](#15-post-deployment-verification-checklist) passes on a preview deployment, the status becomes **READY WITH LIMITATIONS**: Beta Services, 300 s requests, and cold-start schema bootstrap.
