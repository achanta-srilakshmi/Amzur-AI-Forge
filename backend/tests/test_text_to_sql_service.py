import pytest

from app.services.text_to_sql_service import (
    _extract_sql,
    _validate_safe_sql,
    detect_database_query_intent,
)


def test_extract_sql_from_markdown_fence() -> None:
    raw = "```sql\nSELECT id, email FROM users;\n```"
    assert _extract_sql(raw) == "SELECT id, email FROM users"


def test_validate_safe_sql_rejects_delete() -> None:
    with pytest.raises(ValueError):
        _validate_safe_sql("DELETE FROM users")


def test_validate_safe_sql_accepts_select() -> None:
    sql = "SELECT id, title FROM threads"
    assert _validate_safe_sql(sql) == sql


@pytest.mark.asyncio
async def test_detect_database_query_intent_keyword_hit() -> None:
    result = await detect_database_query_intent(
        "Show me the top 10 users from the database", "user@amzur.com"
    )
    assert result is True
