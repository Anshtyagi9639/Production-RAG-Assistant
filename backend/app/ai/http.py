"""HTTP client for the OpenAI SDK.

The SDK's HTTP library (httpx2) verifies certificates through `truststore` by default. On
Windows that calls the system certificate API during the TLS handshake, synchronously on the
event loop, and that API can fetch revocation data over the network with no timeout: one
stalled fetch froze the whole worker (no jobs, no polling, and no asyncio timeout can fire
while the loop itself is blocked).

This client verifies with OpenSSL instead: the same full checks (certificate chain and host
name), done in-process with no network calls during the handshake.
"""

import ssl

import certifi
import httpx2


def openai_ssl_context() -> ssl.SSLContext:
    """Full verification against the system trust store plus the certifi CA bundle."""
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


def create_openai_http_client(timeout_seconds: float) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(verify=openai_ssl_context(), timeout=timeout_seconds)
