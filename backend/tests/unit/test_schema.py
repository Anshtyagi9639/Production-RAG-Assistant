"""Schema checks that need no database: models meet BUILD.md section 5; migration matches them."""

import io
import re

from alembic import command
from sqlalchemy import PrimaryKeyConstraint, Table, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

import app.models  # noqa: F401  (registers every table)
from app.db.base import Base
from tests.helpers import EXPECTED_TABLES, alembic_config

OFFLINE_URL = "postgresql+asyncpg://user:pass@localhost/offline"


def _offline_sql(*args: str) -> str:
    config = alembic_config(OFFLINE_URL)
    buffer = io.StringIO()
    config.output_buffer = buffer
    if args[0] == "upgrade":
        command.upgrade(config, args[1], sql=True)
    else:
        command.downgrade(config, args[1], sql=True)
    return buffer.getvalue()


def _normalize(sql: str) -> tuple[dict[str, set[str]], set[str]]:
    """Split DDL into {table: set of column/constraint lines} and a set of CREATE INDEX lines."""
    tables: dict[str, set[str]] = {}
    indexes: set[str] = set()
    sql = "\n".join(line for line in sql.splitlines() if not line.startswith("--"))
    for statement in sql.split(";"):
        statement = statement.strip()
        if match := re.match(r"CREATE TABLE (\w+) \((.*)\)$", statement, re.DOTALL):
            lines = {line.strip().rstrip(",").strip() for line in match.group(2).splitlines()}
            tables[match.group(1)] = lines - {""}
        elif statement.startswith("CREATE INDEX"):
            indexes.add(" ".join(statement.split()))
    tables.pop("alembic_version", None)
    return tables, indexes


def _model_ddl() -> str:
    dialect = postgresql.dialect()
    statements = []
    for table in Base.metadata.sorted_tables:
        statements.append(str(CreateTable(table).compile(dialect=dialect)))
        statements.extend(
            str(CreateIndex(index).compile(dialect=dialect)) for index in table.indexes
        )
    return ";\n".join(statements)


def test_models_define_exactly_the_planned_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_every_table_has_uuid_id_and_timestamps() -> None:
    for table in Base.metadata.tables.values():
        assert [column.name for column in table.primary_key] == ["id"], table.name
        assert table.c.id.type.compile(dialect=postgresql.dialect()) == "UUID", table.name
        for column in ("created_at", "updated_at"):
            assert table.c[column].type.timezone, f"{table.name}.{column}"
            assert table.c[column].server_default is not None, f"{table.name}.{column}"


def _leading_indexed_columns(table: Table) -> set[str]:
    leading = {next(iter(index.columns)).name for index in table.indexes}
    leading |= {
        next(iter(constraint.columns)).name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint | PrimaryKeyConstraint)
    }
    return leading


def test_every_foreign_key_is_the_leading_column_of_an_index() -> None:
    for table in Base.metadata.tables.values():
        indexed = _leading_indexed_columns(table)
        for foreign_key in table.foreign_keys:
            assert foreign_key.parent.name in indexed, f"{table.name}.{foreign_key.parent.name}"


def test_every_foreign_key_has_a_deliberate_on_delete() -> None:
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.ondelete in {"CASCADE", "SET NULL"}, (
                f"{table.name}.{foreign_key.parent.name}"
            )


def test_migration_creates_the_same_schema_as_the_models() -> None:
    migration_tables, migration_indexes = _normalize(_offline_sql("upgrade", "head"))
    model_tables, model_indexes = _normalize(_model_ddl())

    assert set(migration_tables) == EXPECTED_TABLES
    for name in EXPECTED_TABLES:
        assert migration_tables[name] == model_tables[name], name
    assert migration_indexes == model_indexes


def test_migration_downgrade_drops_every_table() -> None:
    sql = _offline_sql("downgrade", "head:base")

    assert set(re.findall(r"DROP TABLE (\w+)", sql)) == EXPECTED_TABLES
