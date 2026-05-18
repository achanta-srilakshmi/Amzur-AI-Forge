"""Repository helpers for read-only SQL execution and schema introspection."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, datetime, time
import uuid

from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

_MAX_SCHEMA_TABLES = 30


@dataclass(slots=True)
class QueryExecutionResult:
    columns: list[str]
    rows: list[dict[str, str | int | float | bool | None]]


def _build_sync_db_url() -> str:
    """Build a psycopg2 sync URL from configured database settings."""
    db_url = settings.SYNC_DATABASE_URL
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return db_url


@contextmanager
def _sync_engine() -> Iterator[Engine]:
    engine = create_engine(_build_sync_db_url(), pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


def _to_json_value(value: object) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def get_schema_context() -> str:
    """Return compact schema text (tables, columns, and FKs) for prompt context."""
    with _sync_engine() as engine:
        sql_db = SQLDatabase(engine=engine)
        table_names = list(sql_db.get_usable_table_names())[:_MAX_SCHEMA_TABLES]
        if not table_names:
            return "No tables found in database schema."
        return sql_db.get_table_info(table_names=table_names)


def execute_select_query(sql_query: str, *, row_limit: int = 200) -> QueryExecutionResult:
    """Execute a validated SELECT query and return JSON-serializable rows."""
    wrapped_query = f"SELECT * FROM ({sql_query}) AS amzur_sql_result LIMIT {row_limit}"

    with _sync_engine() as engine:
        with engine.connect() as conn:
            result = conn.execute(text(wrapped_query))
            columns = list(result.keys())
            rows: list[dict[str, str | int | float | bool | None]] = []
            for row in result:
                rows.append({
                    col: _to_json_value(val)
                    for col, val in zip(columns, row)
                })
            return QueryExecutionResult(columns=columns, rows=rows)
