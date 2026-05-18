import io
import uuid
from types import SimpleNamespace
from typing import cast

import pandas as pd
import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.ask_data_service as ask_data_service
from app.models.user import User


async def _noop_save_links(*_args: object, **_kwargs: object) -> list[object]:
    return []


def _make_user() -> User:
    return cast(User, SimpleNamespace(id=uuid.uuid4(), email="data.user@amzur.com"))


def _make_db() -> AsyncSession:
    return cast(AsyncSession, SimpleNamespace())


def _error_code(exc: pytest.ExceptionInfo[HTTPException]) -> str:
    detail = cast(dict[str, str], exc.value.detail)
    return detail["error"]


def _make_upload(filename: str, payload: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(payload))


@pytest.mark.asyncio
async def test_run_ask_data_query_file_mode_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_agent(question: str, dataframe: pd.DataFrame, user_email: str) -> dict[str, str]:
        captured["question"] = question
        captured["columns"] = list(dataframe.columns)
        captured["rows"] = len(dataframe)
        captured["email"] = user_email
        return {
            "question": question,
            "pandas_operation": "df.groupby('region')['sales'].mean()",
            "answer": "ok",
        }

    monkeypatch.setattr(ask_data_service, "run_ask_data_agent", _fake_agent)
    monkeypatch.setattr(ask_data_service, "save_external_source_links", _noop_save_links)

    user = _make_user()
    file = _make_upload("sales.csv", b"region,sales\nEast,10\nWest,20\n")

    result = await ask_data_service.run_ask_data_query(
        question="average sales by region",
        input_method="file",
        current_user=user,
        db=_make_db(),
        file=file,
    )

    assert result["answer"] == "ok"
    assert captured["question"] == "average sales by region"
    assert captured["columns"] == ["region", "sales"]
    assert captured["rows"] == 2
    assert captured["email"] == "data.user@amzur.com"


@pytest.mark.asyncio
async def test_run_ask_data_query_file_mode_requires_file() -> None:
    user = _make_user()

    with pytest.raises(HTTPException) as exc:
        await ask_data_service.run_ask_data_query(
            question="average sales by region",
            input_method="file",
            current_user=user,
            db=_make_db(),
            file=None,
        )

    assert exc.value.status_code == 422
    assert _error_code(exc) == "file_required"


@pytest.mark.asyncio
async def test_run_ask_data_query_file_mode_rejects_unsupported_extension() -> None:
    user = _make_user()
    file = _make_upload("sales.json", b"{}")

    with pytest.raises(HTTPException) as exc:
        await ask_data_service.run_ask_data_query(
            question="average sales by region",
            input_method="file",
            current_user=user,
            db=_make_db(),
            file=file,
        )

    assert exc.value.status_code == 400
    assert _error_code(exc) == "unsupported_file_type"


@pytest.mark.asyncio
async def test_run_ask_data_query_google_sheet_mode_requires_url() -> None:
    user = _make_user()

    with pytest.raises(HTTPException) as exc:
        await ask_data_service.run_ask_data_query(
            question="top 5 rows",
            input_method="google_sheet",
            current_user=user,
            db=_make_db(),
            google_sheet_url="   ",
        )

    assert exc.value.status_code == 422
    assert _error_code(exc) == "google_sheet_url_required"


@pytest.mark.asyncio
async def test_run_ask_data_query_google_sheet_mode_loads_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_sheet_loader(sheet_url: str) -> tuple[pd.DataFrame, str, str]:
        captured["url"] = sheet_url
        return (
            pd.DataFrame(
                [
                    {"region": "East", "revenue": 100},
                    {"region": "West", "revenue": 250},
                ]
            ),
            "Revenue Workbook",
            "Sheet1",
        )

    def _fake_agent(question: str, dataframe: pd.DataFrame, user_email: str) -> dict[str, str]:
        captured["question"] = question
        captured["rows"] = len(dataframe)
        captured["email"] = user_email
        return {
            "question": question,
            "pandas_operation": "df.sort_values('revenue', ascending=False).head(5)",
            "answer": "ok",
        }

    monkeypatch.setattr(
        ask_data_service,
        "load_google_sheet_url_data",
        _fake_sheet_loader,
    )
    monkeypatch.setattr(ask_data_service, "run_ask_data_agent", _fake_agent)
    monkeypatch.setattr(ask_data_service, "save_external_source_links", _noop_save_links)

    user = _make_user()

    result = await ask_data_service.run_ask_data_query(
        question="show top 5 rows by revenue",
        input_method="google_sheet",
        current_user=user,
        db=_make_db(),
        google_sheet_url="https://docs.google.com/spreadsheets/d/mock-id/edit",
    )

    assert result["answer"] == "ok"
    assert captured["url"] == "https://docs.google.com/spreadsheets/d/mock-id/edit"
    assert captured["question"] == "show top 5 rows by revenue"
    assert captured["rows"] == 2
    assert captured["email"] == "data.user@amzur.com"


@pytest.mark.asyncio
async def test_run_ask_data_query_google_sheet_mode_rejects_empty_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ask_data_service,
        "load_google_sheet_url_data",
        lambda _url: (pd.DataFrame(), "Empty", "Sheet1"),  # type: ignore[reportUnknownLambdaType]
    )

    monkeypatch.setattr(ask_data_service, "save_external_source_links", _noop_save_links)

    user = _make_user()

    with pytest.raises(HTTPException) as exc:
        await ask_data_service.run_ask_data_query(
            question="show top 5 rows by revenue",
            input_method="google_sheet",
            current_user=user,
            db=_make_db(),
            google_sheet_url="https://docs.google.com/spreadsheets/d/mock-id/edit",
        )

    assert exc.value.status_code == 400
    assert _error_code(exc) == "empty_dataset"


def test_coerce_numeric_like_columns_is_dynamic_for_any_header() -> None:
    frame = pd.DataFrame(
        {
            "Any Numeric Header": ["1", "2", "3"],
            "Another Metric": ["10,000", "20,000", "30,000"],
            "Text Label": ["A", "B", "C"],
        }
    )

    coerced = ask_data_service._coerce_numeric_like_columns(frame)

    assert pd.api.types.is_numeric_dtype(coerced["Any Numeric Header"])
    assert pd.api.types.is_numeric_dtype(coerced["Another Metric"])
    assert not pd.api.types.is_numeric_dtype(coerced["Text Label"])
    assert int(coerced["Any Numeric Header"].sum()) == 6
    assert int(coerced["Another Metric"].sum()) == 60000
