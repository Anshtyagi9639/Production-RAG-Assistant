from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Values come from the environment (or a `.env` file)."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "AI Knowledge & Operations Copilot"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000"

    database_url: str
    redis_url: str
    qdrant_url: str
    qdrant_api_key: SecretStr | None = None

    health_check_timeout_seconds: float = 2.0

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
