"""The OpenAI clients verify TLS with OpenSSL, never through `truststore` (whose Windows
backend can block the event loop during the handshake; see app/ai/http.py)."""

import ssl

import httpx2
from pydantic import SecretStr

from app.ai.embeddings import OpenAIEmbedder
from app.ai.http import create_openai_http_client, openai_ssl_context
from app.ai.llm import OpenAIChatLLM
from app.core.config import Settings


def test_context_is_plain_openssl_with_full_verification() -> None:
    context = openai_ssl_context()

    # Exactly ssl.SSLContext: truststore's context is a different class.
    assert type(context) is ssl.SSLContext
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.cert_store_stats()["x509_ca"] > 0


async def test_http_client_carries_the_timeout() -> None:
    client = create_openai_http_client(12.5)
    try:
        assert isinstance(client, httpx2.AsyncClient)
        assert client.timeout.connect == 12.5
        assert client.timeout.read == 12.5
    finally:
        await client.aclose()


def test_embedder_and_llm_use_the_openssl_client(settings: Settings) -> None:
    configured = settings.model_copy(update={"openai_api_key": SecretStr("sk-test-not-a-real-key")})

    embedder = OpenAIEmbedder(configured)
    llm = OpenAIChatLLM(configured)

    for wrapper in (embedder, llm):
        client = wrapper._client
        assert client is not None
        assert isinstance(client.http_async_client, httpx2.AsyncClient)
