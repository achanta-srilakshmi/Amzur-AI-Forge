import json
from typing import cast
from urllib.parse import parse_qs, urlparse

import gspread
import pandas as pd
from fastapi import HTTPException, status
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound

from app.core.config import settings


def _get_gspread_client() -> gspread.Client:
    raw_json = settings.GOOGLE_SERVICE_ACCOUNT_JSON
    if not raw_json:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "google_service_account_not_configured",
                "message": "GOOGLE_SERVICE_ACCOUNT_JSON is not configured.",
            },
        )

    try:
        creds_dict = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "google_service_account_invalid",
                "message": "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.",
            },
        ) from exc

    return gspread.service_account_from_dict(creds_dict)


def _worksheet_to_dataframe(worksheet: gspread.Worksheet) -> pd.DataFrame:
    rows = cast(list[list[str]], worksheet.get_all_values())
    if not rows:
        return pd.DataFrame()

    headers = rows[0]
    data_rows = rows[1:]
    if not data_rows:
        return pd.DataFrame(columns=headers)

    return pd.DataFrame(data_rows, columns=headers)


def load_google_sheet_url_data(
    sheet_url: str,
) -> tuple[pd.DataFrame, str, str]:
    client = _get_gspread_client()

    parsed_url = urlparse(sheet_url)
    query_params = parse_qs(parsed_url.query, keep_blank_values=True)
    fragment_params = parse_qs(parsed_url.fragment, keep_blank_values=True)
    gid_value = (
        query_params.get("gid", [None])[0]
        or fragment_params.get("gid", [None])[0]
    )

    try:
        spreadsheet = client.open_by_url(sheet_url)
    except SpreadsheetNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "google_sheet_not_found_or_not_shared",
                "message": (
                    "Google Sheet not found or not shared with the configured service "
                    "account. Share the sheet with the service-account email in "
                    "GOOGLE_SERVICE_ACCOUNT_JSON."
                ),
            },
        ) from exc
    except Exception as exc:
        error_msg = str(exc)
        if "not supported for this document" in error_msg or "Office file" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_document_type",
                    "message": (
                        "The URL must point to a native Google Sheet, not a converted "
                        "Office file or Drive file. Try creating a new Google Sheet and "
                        "importing the data, then share it with the service account."
                    ),
                },
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "google_sheets_api_error",
                "message": f"Failed to access Google Sheet: {error_msg}",
            },
        ) from exc

    if gid_value is not None:
        try:
            worksheet = spreadsheet.get_worksheet_by_id(int(gid_value))
        except (ValueError, WorksheetNotFound) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "google_sheet_gid_invalid",
                    "message": "The provided Google Sheet gid is invalid or does not exist.",
                },
            ) from exc
    else:
        worksheet = spreadsheet.get_worksheet(0)

    return _worksheet_to_dataframe(worksheet), spreadsheet.title, worksheet.title


def load_sheet_as_dataframe(sheet_name: str) -> pd.DataFrame:
    client = _get_gspread_client()
    spreadsheet = client.open(sheet_name)
    worksheet = spreadsheet.get_worksheet(0)
    return _worksheet_to_dataframe(worksheet)


def load_google_sheet_url_as_dataframe(sheet_url: str) -> pd.DataFrame:
    dataframe, _spreadsheet_title, _worksheet_title = load_google_sheet_url_data(sheet_url)
    return dataframe