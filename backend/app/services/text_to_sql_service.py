"""Text-to-SQL service: intent detection, SQL generation, validation, and execution."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from langchain_core.messages import HumanMessage

from app.ai.llm import llm
from app.repositories.sql_repository import execute_select_query, get_schema_context

logger = logging.getLogger(__name__)

_SQL_PROMPT_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "text_to_sql_system.txt"
_SQL_SYSTEM_PROMPT = _SQL_PROMPT_PATH.read_text(encoding="utf-8").strip()

_DB_INTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(database|postgres|postgresql|sql|table|column|schema|query)\b", re.IGNORECASE),
    re.compile(r"\b(show|list|get|find|count|sum|average|max|min)\b.{0,40}\b(rows|records|entries|users|messages|threads|attachments|documents)\b", re.IGNORECASE),
    re.compile(r"\bhow many\b", re.IGNORECASE),
)

_DB_CLASSIFIER_PROMPT = (
    "Classify whether the user is asking for a database query that should be answered from PostgreSQL data. "
    "Respond with only YES or NO.\n\n"
    "User message: "
)

_FORBIDDEN_SQL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\binsert\b", re.IGNORECASE),
    re.compile(r"\bupdate\b", re.IGNORECASE),
    re.compile(r"\bdelete\b", re.IGNORECASE),
    re.compile(r"\bdrop\b", re.IGNORECASE),
    re.compile(r"\btruncate\b", re.IGNORECASE),
    re.compile(r"\balter\b", re.IGNORECASE),
)

_SQL_MARKER = "[[AMZUR_SQL_RESULT]]"


class SqlSafetyError(ValueError):
    """Raised when generated SQL violates safety rules."""


@dataclass(slots=True)
class TextToSqlResult:
    response_text: str
    generated_sql: str
    columns: list[str]
    rows: list[dict[str, str | int | float | bool | None]]


def _extract_sql(raw_output: str) -> str:
    sql = raw_output.strip()

    fenced = re.search(r"```(?:sql)?\s*(.*?)```", sql, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        sql = fenced.group(1).strip()

    return sql.rstrip(";").strip()


def _validate_safe_sql(sql: str) -> str:
    if not sql:
        raise SqlSafetyError("Generated SQL is empty.")

    lowered = sql.lower()

    if "--" in lowered or "/*" in lowered or "*/" in lowered:
        raise SqlSafetyError("SQL comments are not allowed.")

    if ";" in sql:
        raise SqlSafetyError("Multiple SQL statements are not allowed.")

    for pattern in _FORBIDDEN_SQL_PATTERNS:
        if pattern.search(sql):
            raise SqlSafetyError("Only read-only SELECT queries are permitted.")

    starts_ok = lowered.startswith("select") or lowered.startswith("with")
    if not starts_ok:
        raise SqlSafetyError("Only SELECT/CTE queries are allowed.")

    return sql


def _format_sql_response(
    question: str,
    generated_sql: str,
    columns: list[str],
    rows: list[dict[str, str | int | float | bool | None]],
) -> str:
    row_count = len(rows)
    column_count = len(columns)
    if row_count == 0:
        return f"Query result for: {question}\n\nNo rows returned."

    return (
        f"Query result for: {question}\n\n"
        f"Returned {row_count} row{'s' if row_count != 1 else ''} "
        f"across {column_count} column{'s' if column_count != 1 else ''}."
    )


def _build_stream_metadata(
    generated_sql: str,
    columns: list[str],
    rows: list[dict[str, str | int | float | bool | None]],
) -> str:
    payload: dict[str, Any] = {
        "generated_sql": generated_sql,
        "sql_result": {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        },
    }
    return f"{_SQL_MARKER}{json.dumps(payload, separators=(',', ':'))}"


def _build_sql_generation_prompt(schema_context: str, question: str) -> str:
    return (
        f"{_SQL_SYSTEM_PROMPT}\n\n"
        f"Database schema:\n{schema_context}\n\n"
        f"User request:\n{question}\n\n"
        "Return only a single PostgreSQL SELECT query."
    )


async def detect_database_query_intent(message: str, user_email: str) -> bool:
    cleaned = message.strip()
    if not cleaned:
        return False

    if any(pattern.search(cleaned) for pattern in _DB_INTENT_PATTERNS):
        return True

    try:
        result = await llm.ainvoke(
            [HumanMessage(content=f"{_DB_CLASSIFIER_PROMPT}{cleaned[:500]}")],
            config={"metadata": {"user_email": user_email}},
        )
        raw_content = cast(object, result.content)  # type: ignore[reportUnknownMemberType]
        normalized = (
            " ".join(str(item) for item in cast(list[object], raw_content))
            if isinstance(raw_content, list)
            else str(raw_content)
        )
        return normalized.strip().upper().startswith("YES")
    except Exception as exc:
        logger.warning("DB intent classifier failed, defaulting to non-DB path: %s", exc)
        return False


async def run_text_to_sql(question: str, user_email: str) -> TextToSqlResult:
    schema_context = await asyncio.to_thread(get_schema_context)

    result = await llm.ainvoke(
        [HumanMessage(content=_build_sql_generation_prompt(schema_context, question))],
        config={"metadata": {"user_email": user_email}},
    )
    raw_content = cast(object, result.content)  # type: ignore[reportUnknownMemberType]
    generated_text = (
        " ".join(str(item) for item in cast(list[object], raw_content))
        if isinstance(raw_content, list)
        else str(raw_content)
    )
    generated_sql = _validate_safe_sql(_extract_sql(generated_text))

    execution = await asyncio.to_thread(execute_select_query, generated_sql)

    return TextToSqlResult(
        response_text=_format_sql_response(
            question=question,
            generated_sql=generated_sql,
            columns=execution.columns,
            rows=execution.rows,
        ),
        generated_sql=generated_sql,
        columns=execution.columns,
        rows=execution.rows,
    )


def build_text_to_sql_stream_tail(result: TextToSqlResult) -> str:
    return _build_stream_metadata(
        generated_sql=result.generated_sql,
        columns=result.columns,
        rows=result.rows,
    )
