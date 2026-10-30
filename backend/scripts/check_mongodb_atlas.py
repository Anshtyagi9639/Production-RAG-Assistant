"""Check the MongoDB Atlas connection step by step, with the application's own client.

Run from backend/:  .venv\\Scripts\\python.exe scripts\\check_mongodb_atlas.py

Uses the same settings (.env) and `create_mongo_client` as the API, and prints sanitized
results only: never the URI, user name, password or host names.
"""

import asyncio
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dns.resolver
import pymongo
from pymongo.errors import OperationFailure

from app.core.config import get_settings
from app.db.mongo import create_mongo_client

# 18 AuthenticationFailed; Atlas reports a wrong user name or password as 8000 ("bad auth").
AUTH_FAILURE_CODES = {18, 8000}
AUTH_HINT = (
    "Atlas accepted the connection but rejected the user name or password in MONGODB_URI. In "
    "Atlas, open Security > Database Access, edit the database user, set a password, click "
    "Update User, and put exactly the same password in MONGODB_URI in the repository-root .env "
    "(percent-encode @ : / ? # [ ] % if present). Then restart the backend and the worker: "
    "--reload does not pick up .env changes."
)
TLS_HINT = (
    "Atlas accepts the TCP connection and then aborts the TLS handshake. This is how Atlas "
    "rejects a source IP that is not on the project's IP Access List: in Atlas, open Security > "
    "Network Access and add this machine's current public IP (or check that a temporary entry "
    "hasn't expired). Do not disable TLS or certificate validation."
)


def report(step: str, ok: bool, detail: str = "") -> None:
    print(f"{step:<12} {'PASS' if ok else 'FAIL'}{'  ' + detail if detail else ''}")


async def main() -> int:
    settings = get_settings()
    uri = settings.mongodb_uri.get_secret_value()
    parts = urlsplit(uri)
    host = parts.hostname or ""
    print(
        f"python {sys.version.split()[0]} | {ssl.OPENSSL_VERSION} | pymongo {pymongo.version}\n"
        f"uri: scheme={parts.scheme} credentials={'SET' if parts.password else 'MISSING'} "
        f"database={settings.mongodb_database}\n"
    )

    try:
        nodes = [
            (str(r.target).rstrip("."), r.port)
            for r in dns.resolver.resolve(f"_mongodb._tcp.{host}", "SRV")
        ]
        report("DNS", True, f"{len(nodes)} nodes")
    except Exception as exc:
        report("DNS", False, type(exc).__name__)
        return 1

    context = ssl.create_default_context()
    tls_ok = 0
    for node, port in nodes:
        label = node.split(".")[0].rsplit("-", 3)[-3:]
        try:
            with (
                socket.create_connection((node, port), timeout=8) as sock,
                context.wrap_socket(sock, server_hostname=node) as tls,
            ):
                tls_ok += 1
                name = "-".join(label)
                print(f"  {name}: TCP ok, TLS ok ({tls.version()}, certificate verified)")
        except ssl.SSLError as exc:
            print(f"  {'-'.join(label)}: TCP ok, TLS rejected ({exc.reason})")
        except OSError as exc:
            print(f"  {'-'.join(label)}: TCP failed ({type(exc).__name__})")
    report("TLS", tls_ok == len(nodes), f"{tls_ok}/{len(nodes)} nodes")
    if tls_ok == 0:
        print(f"\n{TLS_HINT}")
        return 1

    client = create_mongo_client(settings, appname="copilot-atlas-check")
    try:
        await client.admin.command("ping")
        report("Mongo Ping", True)
        database = client[settings.mongodb_database]
        stats = await database.command("dbStats")
        report("Database", True, f"{stats['collections']} collections")
        names = await database.list_collection_names()
        report("Collections", True, ", ".join(sorted(names)))
        users = await database["users"].count_documents({})
        report("Users read", True, f"{users} users")
    except OperationFailure as exc:
        if exc.code in AUTH_FAILURE_CODES:
            report("Mongo Auth", False, f"authentication failed (code {exc.code})")
            print(f"\n{AUTH_HINT}")
        else:
            report("Mongo", False, f"OperationFailure code {exc.code}")
        return 1
    except Exception as exc:
        report("Mongo", False, type(exc).__name__)
        return 1
    finally:
        await client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
