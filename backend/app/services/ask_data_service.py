"""Service layer for Ask your Data DataFrame queries."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from openai import OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chains.ask_data_chain import run_ask_data_agent
from app.models.user import User
from app.repositories.external_source_link_repository import save_external_source_links
from app.services.external_source_link_service import extract_shared_source_links
from app.services.sheets_service import load_google_sheet_url_data

_ALLOWED_FILE_EXTENSIONS = {".csv", ".xlsx"}


def _is_title_question(question: str) -> bool:
    normalized = question.strip().lower()
    if "title" in normalized:
        return True
    if re.search(r"\b(name|sheet\s*name)\b", normalized):
        return True
    return False


def _is_column_names_question(question: str) -> bool:
    normalized = question.strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "column name",
            "column names",
            "columns",
            "headers",
            "header names",
            "fields",
            "schema",
        )
    )


def _read_uploaded_dataframe(file: UploadFile) -> pd.DataFrame:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in _ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unsupported_file_type",
                "message": "Only .csv and .xlsx files are supported.",
            },
        )

    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "empty_file",
                "message": "Uploaded file is empty.",
            },
        )

    if extension == ".csv":
        return pd.read_csv(io.BytesIO(file_bytes))

    return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")


def _validate_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "empty_dataset",
                "message": "The provided dataset has no rows.",
            },
        )

    if len(dataframe.columns) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_dataset",
                "message": "The provided dataset has no columns.",
            },
        )

    return dataframe


def _coerce_numeric_like_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convert columns with fully numeric non-empty values to numeric dtype.

    Google Sheets values are read as strings, which can cause concatenation for sum
    operations. This keeps text columns untouched while making numeric aggregations reliable.
    """
    normalized = dataframe.copy()

    for column in normalized.columns:
        series = normalized[column]

        if pd.api.types.is_numeric_dtype(series):
            continue

        text_values = series.astype(str).str.strip()
        non_empty_mask = text_values != ""
        if not non_empty_mask.any():
            continue

        # Allow values like "43,521" to convert to numbers.
        cleaned = text_values.str.replace(",", "", regex=False)
        numeric = pd.to_numeric(cleaned, errors="coerce")

        # Only coerce when every non-empty value is numeric-like.
        if numeric[non_empty_mask].notna().all():
            normalized[column] = numeric

    return normalized


async def run_ask_data_query(
    question: str,
    input_method: str,
    current_user: User,
    db: AsyncSession,
    file: UploadFile | None = None,
    google_sheet_url: str | None = None,
) -> dict[str, str]:
    trimmed_question = question.strip()
    if not trimmed_question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_question", "message": "Question is required."},
        )

    try:
        source_title: str | None = None
        worksheet_title: str | None = None

        if input_method == "file":
            if file is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "file_required",
                        "message": "A CSV or XLSX file is required for file mode.",
                    },
                )
            source_title = (file.filename or "Uploaded file").strip() or "Uploaded file"
            dataframe = _coerce_numeric_like_columns(
                _validate_dataframe(_read_uploaded_dataframe(file))
            )
        elif input_method == "google_sheet":
            if not google_sheet_url or not google_sheet_url.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "google_sheet_url_required",
                        "message": "Google Sheet URL is required for google_sheet mode.",
                    },
                )
            normalized_sheet_url = google_sheet_url.strip()
            links_to_persist = extract_shared_source_links(normalized_sheet_url)
            if links_to_persist:
                await save_external_source_links(
                    db,
                    user_id=current_user.id,
                    links=links_to_persist,
                )
            dataframe, source_title, worksheet_title = load_google_sheet_url_data(
                normalized_sheet_url
            )
            dataframe = _coerce_numeric_like_columns(_validate_dataframe(dataframe))
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "invalid_input_method",
                    "message": "input_method must be one of: file, google_sheet",
                },
            )

        if _is_title_question(trimmed_question):
            if input_method == "google_sheet":
                spreadsheet_label = source_title or "Unknown"
                worksheet_label = worksheet_title or "Unknown"
                answer = (
                    f"Spreadsheet title: {spreadsheet_label}. "
                    f"Worksheet title: {worksheet_label}."
                )
            else:
                answer = f"Uploaded file title: {source_title or 'Unknown'}."

            return {
                "question": trimmed_question,
                "pandas_operation": "",
                "answer": answer,
            }

        if _is_column_names_question(trimmed_question):
            columns = [str(column) for column in dataframe.columns]
            answer = "Columns: " + ", ".join(columns)
            return {
                "question": trimmed_question,
                "pandas_operation": "",
                "answer": answer,
            }

        return run_ask_data_agent(trimmed_question, dataframe, current_user.email)
    except HTTPException:
        raise
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "llm_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "unexpected", "message": str(exc)},
        ) from exc
