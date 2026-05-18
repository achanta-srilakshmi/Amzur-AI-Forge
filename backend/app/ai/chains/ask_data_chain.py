"""Ask-Data chain built on LangChain's Pandas DataFrame agent."""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

from app.ai.llm import llm

logger = logging.getLogger(__name__)


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _build_column_map(dataframe: pd.DataFrame) -> dict[str, str]:
    return {_normalize_key(str(column)): str(column) for column in dataframe.columns}


def _is_row_detail_question(normalized_question: str) -> bool:
    detail_terms = ("row", "record", "detail", "details", "all columns", "entire", "full", "complete")
    table_terms = ("tabular", "table", "format")
    has_detail_intent = any(term in normalized_question for term in detail_terms)
    asks_for_table = any(term in normalized_question for term in table_terms)
    return has_detail_intent and asks_for_table or "entire row" in normalized_question


def _is_row_count_question(normalized_question: str) -> bool:
    count_terms = ("how many rows", "row count", "number of rows", "record count", "how many records")
    return any(term in normalized_question for term in count_terms)


def _extract_id_value(normalized_question: str) -> str | None:
    patterns = (
        r"(?:\bid\b|transaction\s*id|transactionid|transcation\s*id|transcationid)\s*(?:=|:|is|for)?\s*(\d+)",
        r"(\d+)\s*(?:\btransaction\s*id\b|\btransactionid\b|\btranscation\s*id\b|\btranscationid\b|\bid\b)",
        r"(?:\btransaction\s*id\b|\btransactionid\b|\btranscation\s*id\b|\btranscationid\b).*?\bvalue\b\s*(\d+)",
    )

    for pattern in patterns:
        id_match = re.search(pattern, normalized_question)
        if id_match:
            return id_match.group(1)

    # Last resort: if question clearly asks by id and includes numbers, use the first long number.
    if any(term in normalized_question for term in (" id", "transaction", "transcation")):
        generic_match = re.search(r"\b(\d{4,})\b", normalized_question)
        if generic_match:
            return generic_match.group(1)

    return None


def _looks_like_not_found_answer(answer: str) -> bool:
    normalized = answer.strip().lower()
    signals = (
        "does not exist",
        "no rows",
        "not found",
        "there are no rows",
        "no matching",
    )
    return any(signal in normalized for signal in signals)


def _find_identifier_column(dataframe: pd.DataFrame) -> str | None:
    preferred = ("transactionid", "id")
    for column in dataframe.columns:
        normalized = _normalize_key(str(column))
        if normalized in preferred:
            return str(column)

    for column in dataframe.columns:
        normalized = _normalize_key(str(column))
        if normalized.endswith("id") or "id" in normalized:
            return str(column)

    return None


def _find_requested_column(question: str, dataframe: pd.DataFrame, identifier_column: str | None) -> str | None:
    question_compact = _normalize_key(question)
    best_column: str | None = None
    best_score = -1

    for column in dataframe.columns:
        column_name = str(column)
        if identifier_column and column_name == identifier_column:
            continue

        normalized = _normalize_key(column_name)
        if not normalized:
            continue

        # Match either compact token presence or word-level presence.
        if normalized in question_compact or column_name.lower() in question.lower():
            if len(normalized) > best_score:
                best_score = len(normalized)
                best_column = column_name

    return best_column


def _to_markdown_table(dataframe: pd.DataFrame) -> str:
    headers = [str(col) for col in dataframe.columns]
    header_row = "| " + " | ".join(headers) + " |"
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_rows = [
        "| " + " | ".join(str(row.get(col, "")) for col in headers) + " |"
        for row in dataframe.to_dict(orient="records")
    ]
    return "\n".join([header_row, separator_row, *data_rows])


def _extract_answer(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()

    if not isinstance(result, dict):
        return str(result).strip()

    for key in ("output", "answer", "final_answer", "result"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _deterministic_fallback(question: str, dataframe: pd.DataFrame) -> tuple[str, str]:
    normalized_question = question.strip().lower()

    if _is_row_count_question(normalized_question):
        return "", str(len(dataframe.index))

    id_value = _extract_id_value(normalized_question)
    if id_value:
        identifier_column = _find_identifier_column(dataframe)
        if identifier_column:
            matching_rows = dataframe[dataframe[identifier_column].astype(str).str.strip() == id_value]
            if not matching_rows.empty:
                if _is_row_detail_question(normalized_question):
                    operation = f"df.loc[df['{identifier_column}'].astype(str).str.strip() == '{id_value}']"
                    return operation, _to_markdown_table(matching_rows.head(1))

                requested_column = _find_requested_column(question, dataframe, identifier_column)
                if requested_column:
                    value = str(matching_rows.iloc[0][requested_column])
                    operation = (
                        f"df.loc[df['{identifier_column}'].astype(str).str.strip() == '{id_value}', '{requested_column}'].iloc[0]"
                    )
                    return operation, value

                # If a specific column is not detected, return the full matched row.
                operation = f"df.loc[df['{identifier_column}'].astype(str).str.strip() == '{id_value}']"
                return operation, _to_markdown_table(matching_rows.head(1))

    return "", ""


def _extract_pandas_operation(intermediate_steps: list[tuple[Any, Any]]) -> str:
    for action, _observation in reversed(intermediate_steps):
        tool_input = getattr(action, "tool_input", "")

        if isinstance(tool_input, dict):
            for value in tool_input.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()

        if isinstance(tool_input, str) and tool_input.strip():
            return tool_input.strip()

        log_text = getattr(action, "log", "")
        if isinstance(log_text, str) and log_text.strip():
            return log_text.strip()

    return ""


def run_ask_data_agent(question: str, dataframe: pd.DataFrame, user_email: str) -> dict[str, str]:
    pandas_agent = create_pandas_dataframe_agent(
        llm=llm,
        df=dataframe,
        agent_type="tool-calling",
        verbose=False,
        allow_dangerous_code=True,
        return_intermediate_steps=True,
        max_iterations=15,
        agent_executor_kwargs={"handle_parsing_errors": True},
    )

    result = pandas_agent.invoke(
        {"input": question},
        config={"metadata": {"user_email": user_email}},
    )

    intermediate_steps = result.get("intermediate_steps", []) if isinstance(result, dict) else []
    pandas_operation = _extract_pandas_operation(intermediate_steps)

    answer = _extract_answer(result)

    if not answer and isinstance(intermediate_steps, list) and intermediate_steps:
        last_observation = intermediate_steps[-1][1]
        if isinstance(last_observation, str) and last_observation.strip():
            answer = last_observation.strip()

    fallback_operation, fallback_answer = _deterministic_fallback(question, dataframe)
    should_use_fallback = not answer or _looks_like_not_found_answer(answer)
    if should_use_fallback and fallback_answer:
        if fallback_operation and not pandas_operation:
            pandas_operation = fallback_operation
        answer = fallback_answer

    logger.info("ask_data result keys: %s", list(result.keys()) if isinstance(result, dict) else type(result))
    logger.info("ask_data answer: %r", answer)
    logger.info("ask_data intermediate_steps count: %d", len(intermediate_steps))

    return {
        "question": question,
        "pandas_operation": pandas_operation,
        "answer": answer,
    }
