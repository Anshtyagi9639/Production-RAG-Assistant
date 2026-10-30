import os

from app.core.config import Settings


def configure_tracing(settings: Settings) -> None:
    """LangSmith reads its configuration from the process environment, while Settings reads
    .env without exporting it. Export it here, from the one settings object, so tracing is on
    exactly when LANGSMITH_TRACING=true and a key is set (and off otherwise)."""
    api_key = settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else ""
    if settings.langsmith_tracing and api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
