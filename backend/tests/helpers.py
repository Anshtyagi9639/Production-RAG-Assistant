from pathlib import Path

from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]

EXPECTED_TABLES = {
    "users",
    "workspaces",
    "workspace_members",
    "documents",
    "document_chunks",
    "conversations",
    "messages",
    "agent_runs",
    "activity_logs",
}


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    # alembic.ini is parsed by configparser, which treats "%" as interpolation.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    # Keep pytest's logging setup instead of applying alembic.ini's.
    config.attributes["configure_logger"] = False
    return config
