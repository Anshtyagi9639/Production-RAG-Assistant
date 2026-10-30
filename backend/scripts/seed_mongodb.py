"""Seed MongoDB Atlas with synthetic development data. Idempotent: safe to run repeatedly.

Run from the repository root:

    python backend/scripts/seed_mongodb.py                 # create schema + upsert seed data
    python backend/scripts/seed_mongodb.py --index-vectors # also embed seed chunks into Qdrant
    python backend/scripts/seed_mongodb.py --export-json   # regenerate backend/seed_data/*.json
    python backend/scripts/seed_mongodb.py --reset         # delete only the seed records

Uses the application's settings (app.core.config.Settings, read from the repository-root .env)
plus SEED_ADMIN_PASSWORD / SEED_MEMBER_PASSWORD, which only this script reads. Never prints
connection strings or secrets.
All content is synthetic development/demo data, not official or client information.
"""

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from pydantic import SecretStr  # noqa: E402
from pydantic_settings import SettingsConfigDict  # noqa: E402
from pymongo import AsyncMongoClient  # noqa: E402
from pymongo.asynchronous.database import AsyncDatabase  # noqa: E402
from pymongo.errors import DuplicateKeyError  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.security import hash_password, verify_password  # noqa: E402
from app.db.mongo import create_mongo_client  # noqa: E402
from app.db.mongo_schema import COLLECTIONS, ensure_schema  # noqa: E402
from app.models.enums import (  # noqa: E402
    AgentRunStatus,
    DocumentStatus,
    MessageRole,
    WorkspaceRole,
)
from app.rag.chunking import chunk_pages  # noqa: E402
from app.rag.extraction import Page  # noqa: E402

SEED_DATA_DIR = BACKEND / "seed_data"
# Fixed namespace: every seed record has a deterministic UUID, so re-runs update in place.
SEED_NAMESPACE = uuid.UUID("6f1d3c2e-4b5a-4c8d-9e0f-1a2b3c4d5e6f")
BASE_TIME = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
MIN_PASSWORD_LENGTH = 8

DEMO_DOCUMENT = """\
CUSTOMS WISE DEMO KNOWLEDGE BASE
DEVELOPMENT / DEMO CONTENT ONLY. This text is synthetic sample material written to exercise the
application. It is not official customs guidance and not client information. Always confirm
requirements with the relevant customs authority before acting on anything described here.

1. Customs clearance overview
Customs clearance is the process of getting goods released by the customs authority when they
cross a border. In this demo scenario, a shipment is declared to customs with a description of
the goods, their commodity code, their value and their origin. The authority checks the
declaration, may inspect the goods, calculates any duties and taxes, and then releases the
shipment once everything is settled. Delays usually come from incomplete paperwork, unclear
product descriptions or values that do not match the commercial invoice. A broker or freight
forwarder often prepares the declaration on behalf of the importer, but the importer remains
responsible for the accuracy of the information. Good practice in this demo is to keep one
shipment folder per consignment containing the invoice, packing list, transport document and
any certificates, so that questions from customs can be answered quickly. Clearance times in the
scenario range from a few hours for routine low-risk shipments to several days when a physical
inspection is selected. Tracking the declaration status and responding promptly to queries are
the two habits that shorten clearance the most in this example knowledge base.

2. Import documentation
For a typical import in this demo, the importer prepares a commercial invoice that states the
seller, the buyer, a clear description of each item, quantities, unit prices, the currency and
the agreed delivery terms. A packing list accompanies the invoice and shows how the goods are
packed, with weights and dimensions for each package. The transport document depends on the
mode of transport: a bill of lading for sea freight, an air waybill for air freight, or a road
consignment note for trucks. Where a preferential duty rate is claimed, a proof of origin is
needed, such as an origin statement on the invoice or a certificate issued by an authorised
body. Some goods also need licences or permits before they can be imported. In the demo
workflow, the documents are checked for consistency before submission: the description,
quantity and value must match across the invoice, packing list and declaration. Missing or
inconsistent documents are the most common reason the demo team sees a declaration rejected or
held for review, so the checklist approach described here is used for every import.

3. Export documentation
Exports in this demo follow a similar pattern in reverse. The exporter issues a commercial
invoice and packing list, and the export declaration is lodged before the goods leave. The
declaration records the exporter, the consignee, the commodity code, the value and the
destination. Some products are subject to export controls, for example items with possible
military or dual-use applications, and these need an export licence before shipment. When the
buyer wants to claim preferential treatment in the destination country, the exporter provides
the appropriate proof of origin and keeps supporting evidence that the goods meet the rules of
origin. In the demo process, the exporter also keeps evidence that the goods actually left the
country, such as the exit confirmation, because this may be needed to justify a zero-rated
sale for tax purposes. Keeping copies of every export document for the required retention
period is part of the demo checklist, so that later audits can be answered without searching
through emails.

4. Customs compliance
Compliance in this demo means declaring goods correctly and being able to prove it later. The
key points are the commodity classification, the customs value and the origin of the goods.
Classification determines the duty rate and whether any restrictions apply, so the demo team
records the reasoning behind each classification decision. The customs value is normally based
on the price actually paid, adjusted for items such as freight, insurance, royalties or assists
where required. Origin rules decide whether preferential rates can be used. The demo company
runs periodic internal reviews that compare a sample of declarations with the underlying
invoices and transport documents, and it corrects errors through the voluntary disclosure
process described by the authority. Training the people who prepare declarations, keeping
product data up to date and documenting decisions are the practices this knowledge base treats
as the foundation of a compliant import and export operation.

5. Food customs requirements
Food products in this demo scenario usually face extra checks beyond the standard customs
procedure. Depending on the product, the importer may need health certificates issued in the
country of origin, prior notification to the food safety authority before arrival, and
entry through a designated border control point that can perform documentary, identity and
physical checks. Labels must meet the destination market's rules on language, ingredients,
allergens and nutrition information. Products of animal origin are generally subject to the
strictest controls in the demo, while some plant products need phytosanitary certificates.
Temperature-controlled goods require evidence that the cold chain was maintained. In the demo
workflow, the importer confirms all of these requirements with the competent authorities before
the goods are shipped, because food consignments that arrive without the right certificates may
be held, returned or destroyed at the importer's cost.

6. Customs valuation and duty calculation
In this demo, import duty is usually calculated as a percentage of the customs value, although
some goods carry specific duties based on weight or quantity instead. The starting point is the
transaction value: the price paid or payable for the goods when sold for export to the
destination. The demo team then checks whether adjustments are required. Costs of transport and
insurance up to the point of entry are typically added, as are buying commissions in some cases,
royalties and licence fees connected to the goods, and the value of tools or materials supplied
free of charge to the producer. Discounts given before importation may be deducted when they are
genuine and documented. Once the customs value is known, the duty rate linked to the commodity
code is applied, and import VAT or similar taxes are calculated on top of the duty-inclusive
value. The demo knowledge base recommends keeping a valuation worksheet for each recurring
supplier so that the same adjustments are applied consistently, and reviewing it whenever the
commercial terms change, for example when the delivery terms move from one Incoterm to another.

7. Bonded warehousing and duty deferral
The demo company sometimes stores imported goods in a bonded warehouse instead of releasing them
straight into free circulation. While the goods remain in the bonded warehouse, duties and
import taxes are suspended, which helps cash flow when goods are held for a long time or may be
re-exported. When goods leave the warehouse for the domestic market, the duty becomes payable at
that point. Goods that are re-exported directly from the warehouse never pay import duty. The
warehouse keeper must keep accurate stock records that reconcile with the customs declarations,
and the authority can audit these records at any time. In this demo scenario, the logistics team
reviews warehouse stock reports every month and compares them with the declarations lodged for
goods entering and leaving the warehouse, so that any discrepancy is investigated before an
audit finds it. This section, like the rest of the document, is synthetic demo material.

8. Record keeping and audits
The demo company keeps customs records for the full retention period required by the authority.
Records include declarations, invoices, transport documents, proofs of origin, licences,
valuation worksheets and correspondence with customs. Each record is stored against the
shipment reference so that it can be retrieved quickly during an audit. Before an audit, the
demo compliance lead prepares a sample of declarations, checks that each one is supported by
complete documents, and notes any corrections that were already disclosed. After the audit, the
team records the findings, agrees actions with the people responsible, and tracks them to
completion. Treating audits as a routine check rather than an exceptional event is the final
practice recommended by this synthetic demo knowledge base.
"""


class SeedSettings(Settings):
    """The application's settings plus the seed-only login passwords."""

    model_config = SettingsConfigDict(env_file=REPO / ".env", extra="ignore")

    seed_admin_password: SecretStr | None = None
    seed_member_password: SecretStr | None = None


def seed_id(name: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, name)


def at(minutes: int) -> datetime:
    return BASE_TIME + timedelta(minutes=minutes)


def _stamp(minutes: int) -> dict[str, datetime]:
    return {"created_at": at(minutes), "updated_at": at(minutes)}


ADMIN = seed_id("user:admin")
MEMBER = seed_id("user:member")
DEMO_WORKSPACE = seed_id("workspace:production-rag-demo")
SANDBOX_WORKSPACE = seed_id("workspace:member-sandbox")
DEMO_DOCUMENT_ID = seed_id("document:customs-wise-demo")
SANDBOX_DOCUMENT_ID = seed_id("document:member-sandbox-notes")
CONVERSATION = seed_id("conversation:customs-demo")
AGENT_RUN = seed_id("agent-run:customs-demo")


def build_seed() -> dict[str, list[dict[str, Any]]]:
    """All seed records, keyed by collection. Users carry no password hash here."""
    demo_bytes = DEMO_DOCUMENT.encode("utf-8")
    sandbox_text = (
        "MEMBER SANDBOX NOTES. DEVELOPMENT / DEMO CONTENT ONLY.\n"
        "This document exists only to check that each workspace sees just its own data.\n"
    )
    chunks = chunk_pages([Page(None, DEMO_DOCUMENT)], DEMO_DOCUMENT_ID)
    sandbox_chunks = chunk_pages([Page(None, sandbox_text)], SANDBOX_DOCUMENT_ID)

    def chunk_records(
        document_id: uuid.UUID, workspace_id: uuid.UUID, items: list[Any], minute: int
    ) -> list[dict[str, Any]]:
        return [
            {
                "_id": chunk.id,
                "document_id": document_id,
                "workspace_id": workspace_id,
                "chunk_index": chunk.index,
                "page": chunk.page,
                "text": chunk.text,
                "token_count": chunk.token_count,
                **_stamp(minute),
            }
            for chunk in items
        ]

    def document(
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        uploader: uuid.UUID,
        filename: str,
        data: bytes,
        chunk_count: int,
        minute: int,
    ) -> dict[str, Any]:
        return {
            "_id": document_id,
            "workspace_id": workspace_id,
            "uploaded_by_id": uploader,
            "filename": filename,
            # Same shape as uploads: random-looking hex name + extension, never the filename.
            "storage_key": f"{document_id.hex}.txt",
            "content_type": "text/plain",
            "size_bytes": len(data),
            "status": DocumentStatus.COMPLETED.value,
            "error_message": None,
            "page_count": None,
            "chunk_count": chunk_count,
            "processed_at": at(minute + 1),
            **_stamp(minute),
        }

    return {
        "users": [
            {
                "_id": ADMIN,
                "email": "admin@copilot.example.com",
                "full_name": "Demo Admin",
                "is_active": True,
                **_stamp(0),
            },
            {
                "_id": MEMBER,
                "email": "member@copilot.example.com",
                "full_name": "Demo Member",
                "is_active": True,
                **_stamp(1),
            },
        ],
        "workspaces": [
            {"_id": DEMO_WORKSPACE, "name": "Production RAG Demo", **_stamp(2)},
            {"_id": SANDBOX_WORKSPACE, "name": "Member Sandbox", **_stamp(3)},
        ],
        "workspace_members": [
            {
                "_id": seed_id("member:demo:admin"),
                "workspace_id": DEMO_WORKSPACE,
                "user_id": ADMIN,
                "role": WorkspaceRole.OWNER.value,
                **_stamp(2),
            },
            {
                "_id": seed_id("member:demo:member"),
                "workspace_id": DEMO_WORKSPACE,
                "user_id": MEMBER,
                "role": WorkspaceRole.MEMBER.value,
                **_stamp(4),
            },
            {
                "_id": seed_id("member:sandbox:member"),
                "workspace_id": SANDBOX_WORKSPACE,
                "user_id": MEMBER,
                "role": WorkspaceRole.OWNER.value,
                **_stamp(3),
            },
        ],
        "documents": [
            document(
                DEMO_DOCUMENT_ID,
                DEMO_WORKSPACE,
                ADMIN,
                "customs-wise-demo.txt",
                demo_bytes,
                len(chunks),
                10,
            ),
            document(
                SANDBOX_DOCUMENT_ID,
                SANDBOX_WORKSPACE,
                MEMBER,
                "member-sandbox-notes.txt",
                sandbox_text.encode("utf-8"),
                len(sandbox_chunks),
                12,
            ),
        ],
        "document_chunks": [
            *chunk_records(DEMO_DOCUMENT_ID, DEMO_WORKSPACE, chunks, 11),
            *chunk_records(SANDBOX_DOCUMENT_ID, SANDBOX_WORKSPACE, sandbox_chunks, 13),
        ],
        "conversations": [
            {
                "_id": CONVERSATION,
                "workspace_id": DEMO_WORKSPACE,
                "user_id": ADMIN,
                "title": "Customs Demo Conversation",
                **_stamp(20),
            }
        ],
        "messages": [
            {
                "_id": seed_id("message:customs-demo:1"),
                "conversation_id": CONVERSATION,
                "workspace_id": DEMO_WORKSPACE,
                "role": MessageRole.USER.value,
                "content": "What documents are normally required for customs clearance?",
                "sources": [],
                "insufficient_context": False,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                **_stamp(20),
            },
            {
                "_id": seed_id("message:customs-demo:2"),
                "conversation_id": CONVERSATION,
                "workspace_id": DEMO_WORKSPACE,
                "role": MessageRole.ASSISTANT.value,
                "content": (
                    "This is a development/demo response. Refer to the connected knowledge base "
                    "for verified information."
                ),
                "sources": [],
                "insufficient_context": False,
                # Not produced by the LLM, so no tokens were used.
                "prompt_tokens": 0,
                "completion_tokens": 0,
                **_stamp(21),
            },
        ],
        "agent_runs": [
            {
                "_id": AGENT_RUN,
                "workspace_id": DEMO_WORKSPACE,
                "user_id": ADMIN,
                "request": "Summarise the import and export documentation steps in the demo.",
                "status": AgentRunStatus.COMPLETED.value,
                "classification": "simple",
                "trace": [],
                "final_answer": (
                    "Development/demo agent run created by the seed script; it was not "
                    "generated by the agent."
                ),
                "sources": [],
                "is_partial": False,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "error": None,
                "started_at": at(30),
                "finished_at": at(30),
                **_stamp(30),
            }
        ],
        "activity_logs": [
            _activity(
                "workspace.created",
                ADMIN,
                "workspace",
                DEMO_WORKSPACE,
                2,
                {"name": "Production RAG Demo"},
            ),
            _activity(
                "member.added",
                ADMIN,
                "user",
                MEMBER,
                4,
                {"email": "member@copilot.example.com", "role": WorkspaceRole.MEMBER.value},
            ),
            _activity(
                "document.uploaded",
                ADMIN,
                "document",
                DEMO_DOCUMENT_ID,
                10,
                {"filename": "customs-wise-demo.txt"},
            ),
            _activity(
                "conversation.created",
                ADMIN,
                "conversation",
                CONVERSATION,
                20,
                {"title": "Customs Demo Conversation"},
            ),
        ],
    }


def _activity(
    action: str,
    user: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    minute: int,
    details: dict[str, Any],
    workspace: uuid.UUID = DEMO_WORKSPACE,
) -> dict[str, Any]:
    return {
        "_id": seed_id(f"activity:{action}:{entity_id}"),
        "workspace_id": workspace,
        "user_id": user,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details,
        **_stamp(minute),
    }


# --- JSON export (MongoDB Extended JSON, importable with Atlas Data Explorer) --------------


def _to_extended_json(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return {"$uuid": str(value)}
    if isinstance(value, datetime):
        return {"$date": value.astimezone(UTC).isoformat().replace("+00:00", "Z")}
    if isinstance(value, dict):
        return {key: _to_extended_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_extended_json(item) for item in value]
    return value


def export_json(directory: Path = SEED_DATA_DIR) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for collection, records in build_seed().items():
        path = directory / f"{collection}.json"
        path.write_text(
            json.dumps(_to_extended_json(records), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


# --- Seeding ----------------------------------------------------------------------------


def _required_password(value: SecretStr | None, name: str) -> str:
    password = value.get_secret_value() if value else ""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Set {name} (at least {MIN_PASSWORD_LENGTH} characters) in .env")
    return password


async def _upsert(
    database: AsyncDatabase[dict[str, Any]], collection: str, records: list[dict[str, Any]]
) -> int:
    for record in records:
        fields = {k: v for k, v in record.items() if k not in {"_id", "created_at"}}
        await database[collection].update_one(
            {"_id": record["_id"]},
            {"$set": fields, "$setOnInsert": {"created_at": record["created_at"]}},
            upsert=True,
        )
    return len(records)


async def _set_passwords(
    database: AsyncDatabase[dict[str, Any]], passwords: dict[uuid.UUID, str]
) -> None:
    """Hash with the application's argon2 settings; rehash only if the password changed."""
    for user_id, password in passwords.items():
        user = await database["users"].find_one({"_id": user_id}, {"password_hash": 1})
        if user is None or not verify_password(password, user.get("password_hash")):
            await database["users"].update_one(
                {"_id": user_id}, {"$set": {"password_hash": hash_password(password)}}
            )


def _write_seed_files(settings: SeedSettings, records: dict[str, list[dict[str, Any]]]) -> None:
    """Store the source files under their storage keys so the worker could reprocess them."""
    root = Path(settings.storage_local_path)
    root = root if root.is_absolute() else BACKEND / root
    root.mkdir(parents=True, exist_ok=True)
    texts = {DEMO_DOCUMENT_ID: DEMO_DOCUMENT}
    for document in records["documents"]:
        text = texts.get(document["_id"])
        if text is None:
            chunks = [c for c in records["document_chunks"] if c["document_id"] == document["_id"]]
            text = "\n".join(c["text"] for c in chunks) + "\n"
        (root / document["storage_key"]).write_text(text, encoding="utf-8")


async def _verify(
    database: AsyncDatabase[dict[str, Any]], records: dict[str, list[dict[str, Any]]]
) -> list[str]:
    problems = []
    for collection, items in records.items():
        found = await database[collection].count_documents(
            {"_id": {"$in": [r["_id"] for r in items]}}
        )
        if found != len(items):
            problems.append(f"{collection}: expected {len(items)}, found {found}")
    demo_docs = await database["documents"].distinct("_id", {"workspace_id": DEMO_WORKSPACE})
    sandbox_docs = await database["documents"].distinct("_id", {"workspace_id": SANDBOX_WORKSPACE})
    if DEMO_DOCUMENT_ID in sandbox_docs or SANDBOX_DOCUMENT_ID in demo_docs:
        problems.append("workspace isolation: a document appears in the wrong workspace")
    sandbox_chunks = await database["document_chunks"].count_documents(
        {"workspace_id": SANDBOX_WORKSPACE, "document_id": DEMO_DOCUMENT_ID}
    )
    if sandbox_chunks:
        problems.append("workspace isolation: demo chunks visible in the sandbox workspace")
    return problems


async def _index_vectors(settings: SeedSettings, records: dict[str, list[dict[str, Any]]]) -> str:
    """Embed seed chunks with OpenAI and upsert them into Qdrant via the app's indexing code."""
    from app.ai.embeddings import OpenAIEmbedder
    from app.db.qdrant import create_qdrant
    from app.rag.chunking import Chunk
    from app.rag.indexing import VectorIndex, ensure_collection

    if not settings.openai_key:
        return "BLOCKED: OPENAI_API_KEY is required for --index-vectors"
    embedder = OpenAIEmbedder(settings)
    qdrant = create_qdrant(settings)
    try:
        await ensure_collection(qdrant, settings.embedding_dimensions)
        index = VectorIndex(qdrant)
        indexed = 0
        for document in records["documents"]:
            items = [c for c in records["document_chunks"] if c["document_id"] == document["_id"]]
            chunks = [
                Chunk(
                    id=c["_id"],
                    index=c["chunk_index"],
                    page=c["page"],
                    text=c["text"],
                    token_count=c["token_count"],
                )
                for c in items
            ]
            vectors = await embedder.embed_documents([c.text for c in chunks])
            await index.replace_document(
                document_id=document["_id"],
                workspace_id=document["workspace_id"],
                filename=document["filename"],
                created_at=document["created_at"],
                chunks=chunks,
                vectors=vectors,
            )
            indexed += len(chunks)
        return f"indexed {indexed} chunks in Qdrant"
    finally:
        await qdrant.close()


def _client(settings: SeedSettings) -> AsyncMongoClient[dict[str, Any]]:
    return create_mongo_client(settings, appname="copilot-seed")


async def seed(settings: SeedSettings, index_vectors: bool) -> None:
    passwords = {
        ADMIN: _required_password(settings.seed_admin_password, "SEED_ADMIN_PASSWORD"),
        MEMBER: _required_password(settings.seed_member_password, "SEED_MEMBER_PASSWORD"),
    }
    client = _client(settings)
    try:
        await client.admin.command("ping")
        print("MongoDB Atlas: ping OK")
        database = client[settings.mongodb_database]
        await ensure_schema(database)
        print(f"schema: {len(COLLECTIONS)} collections with validators and indexes ensured")
        records = build_seed()
        try:
            for collection, items in records.items():
                count = await _upsert(database, collection, items)
                print(f"  {collection:18} {count} upserted")
        except DuplicateKeyError as exc:
            conflict = (exc.details or {}).get("keyValue")
            raise SystemExit(
                f"A non-seed record already uses a seed email or key ({conflict}). "
                "Remove it or change the seed data."
            ) from exc
        await _set_passwords(database, passwords)
        _write_seed_files(settings, records)
        problems = await _verify(database, records)
        print("verification:", "PASS" if not problems else "FAIL")
        for problem in problems:
            print("  -", problem)
        if index_vectors:
            print("vectors:", await _index_vectors(settings, records))
        else:
            print("vectors: not indexed (run with --index-vectors to make the demo searchable)")
    finally:
        await client.close()


async def reset(settings: SeedSettings) -> None:
    """Delete only the records this script creates (matched by their deterministic ids)."""
    client = _client(settings)
    try:
        database = client[settings.mongodb_database]
        for collection, items in build_seed().items():
            result = await database[collection].delete_many(
                {"_id": {"$in": [r["_id"] for r in items]}}
            )
            print(f"  {collection:18} {result.deleted_count} deleted")
    finally:
        await client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--export-json", action="store_true", help="write backend/seed_data/*.json")
    group.add_argument("--reset", action="store_true", help="delete the seed records")
    parser.add_argument(
        "--index-vectors", action="store_true", help="embed seed chunks into Qdrant"
    )
    args = parser.parse_args(argv)

    if args.export_json:
        for path in export_json():
            print("wrote", path.relative_to(REPO))
        return
    settings = SeedSettings()
    action: Callable[[], Any] = (
        (lambda: reset(settings)) if args.reset else (lambda: seed(settings, args.index_vectors))
    )
    asyncio.run(action())


if __name__ == "__main__":
    main()
