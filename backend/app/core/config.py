from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
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

    # Auth
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_expire_minutes: int = Field(default=60, ge=1)

    # Uploads and file storage
    max_upload_mb: int = Field(default=20, ge=1)
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "storage/uploads"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "auto"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None

    # Embeddings and retrieval
    openai_api_key: SecretStr | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = Field(default=64, ge=1)
    embedding_max_attempts: int = Field(default=3, ge=1)
    retrieval_top_k: int = Field(default=6, ge=1, le=50)
    retrieval_score_threshold: float = Field(default=0.3, ge=0, le=1)
    query_embedding_cache_ttl_seconds: int = Field(default=600, ge=0)

    # Worker
    worker_job_timeout_seconds: int = Field(default=600, ge=30)
    worker_max_tries: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def _s3_settings_are_complete(self) -> Self:
        if self.storage_backend == "s3":
            required = {
                "S3_BUCKET": self.s3_bucket,
                "S3_ACCESS_KEY_ID": self.s3_access_key_id,
                "S3_SECRET_ACCESS_KEY": self.s3_secret_access_key,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError(f"STORAGE_BACKEND=s3 requires {', '.join(missing)}")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def openai_key(self) -> str | None:
        """The OpenAI key, or None when unset or empty."""
        value = self.openai_api_key.get_secret_value() if self.openai_api_key else ""
        return value or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
