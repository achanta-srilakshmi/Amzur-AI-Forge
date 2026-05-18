"""NL-to-SQL chain built on LangChain's SQL agent."""

import re
from typing import Any

from fastapi import HTTPException, status
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.base import create_sql_agent

from app.ai.llm import llm
from app.core.config import settings

_MUTATING_KEYWORDS = ("INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER")
_READONLY_TABLES = [
    "users",
    "threads",
    "messages",
    "attachments",
    "documents",
    "generated_images",
]


def _build_sync_db_url() -> str:
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return f"postgresql+psycopg2://{url.removeprefix('postgresql://')}"
    return url


def _block_mutating_sql(question: str) -> None:
    if re.search(r"\b(" + "|".join(_MUTATING_KEYWORDS) + r")\b", question, flags=re.IGNORECASE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unsafe_query",
                "message": "Mutating SQL keywords are not allowed. Ask a read-only question.",
            },
        )


def _extract_sql(intermediate_steps: list[tuple[Any, Any]]) -> str:
    for action, _observation in intermediate_steps:
        tool_name = getattr(action, "tool", "")
        if tool_name != "sql_db_query":
            continue
        tool_input = getattr(action, "tool_input", "")
        if isinstance(tool_input, dict):
            for value in tool_input.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()
        if isinstance(tool_input, str) and tool_input.strip():
            return tool_input.strip()

        log_text = getattr(action, "log", "")
        if isinstance(log_text, str):
            match = re.search(
                r"SQLQuery:\s*(.+?)(?:\nSQLResult:|\nObservation:|$)",
                log_text,
                flags=re.DOTALL,
            )
            if match:
                return match.group(1).strip()
    return ""


def run_nl_to_sql_agent(question: str, user_email: str) -> dict[str, str]:
    _block_mutating_sql(question)

    sql_database = SQLDatabase.from_uri(
        _build_sync_db_url(),
        include_tables=_READONLY_TABLES,
    )
    
    sql_agent = create_sql_agent(
        llm=llm,
        db=sql_database,
        agent_type="zero-shot-react-description",
        verbose=False,
        return_intermediate_steps=True,
        agent_executor_kwargs={"handle_parsing_errors": True},
    )

    try:
        result = sql_agent.invoke(
            {"input": question},
            config={"metadata": {"user_email": user_email}},
        )
    except Exception as exc:
        # Gracefully degrade on agent output parser failures so API callers
        # receive a useful response instead of an internal server error.
        if "output parsing error" in str(exc).lower() or "could not parse llm output" in str(exc).lower():
            return {
                "question": question,
                "sql": "",
                "answer": "I could not determine a reliable SQL answer for that request.",
            }
        raise

    intermediate_steps = result.get("intermediate_steps", [])
    sql = _extract_sql(intermediate_steps)
    answer = str(result.get("output", "")).strip()

    return {
        "question": question,
        "sql": sql,
        "answer": answer,
    }