import asyncio

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  (registers every table)
from app.db.base import Base
from tests.helpers import EXPECTED_TABLES, alembic_config

pytestmark = pytest.mark.integration


def _schema_diff(connection: Connection) -> list[object]:
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    return list(compare_metadata(context, Base.metadata))


async def _inspect(url: str) -> tuple[set[str], str | None, list[object]]:
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as connection:
        tables = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        version = await connection.scalar(text("SELECT max(version_num) FROM alembic_version"))
        diff = await connection.run_sync(_schema_diff)
    await engine.dispose()
    return tables, version, diff


async def test_upgrade_matches_models_and_downgrade_removes_everything(
    test_database_url: str,
) -> None:
    config = alembic_config(test_database_url)

    tables, version, diff = await _inspect(test_database_url)
    assert tables == EXPECTED_TABLES | {"alembic_version"}
    assert version == "0001"
    assert diff == []

    await asyncio.to_thread(command.downgrade, config, "base")
    tables, version, _ = await _inspect(test_database_url)
    assert tables == {"alembic_version"}
    assert version is None

    await asyncio.to_thread(command.upgrade, config, "head")
    tables, version, diff = await _inspect(test_database_url)
    assert tables == EXPECTED_TABLES | {"alembic_version"}
    assert version == "0001"
    assert diff == []
