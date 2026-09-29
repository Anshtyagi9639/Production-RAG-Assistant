from qdrant_client import AsyncQdrantClient

from app.core.config import Settings


def create_qdrant(settings: Settings) -> AsyncQdrantClient:
    api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else ""
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=api_key or None)
