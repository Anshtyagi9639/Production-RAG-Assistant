import pytest

from app.core.config import Settings


def test_allowed_origins_are_split_and_trimmed(settings: Settings) -> None:
    settings.allowed_origins = " http://localhost:3000 , https://app.example.com,,"

    assert settings.cors_origins == ["http://localhost:3000", "https://app.example.com"]


def test_required_connection_urls_must_be_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "REDIS_URL", "QDRANT_URL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="database_url"):
        Settings(_env_file=None)
