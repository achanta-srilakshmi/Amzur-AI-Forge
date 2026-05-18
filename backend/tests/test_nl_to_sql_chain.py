import pytest
from fastapi import HTTPException

import app.ai.chains.nl_to_sql_chain as nl_to_sql_chain
from app.ai.chains.nl_to_sql_chain import _READONLY_TABLES, _block_mutating_sql


REQUIRED_TABLES = {
    "users",
    "threads",
    "messages",
    "attachments",
    "documents",
    "generated_images",
}


@pytest.mark.parametrize("keyword", ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER"])
def test_block_mutating_sql_rejects_forbidden_keywords_case_insensitive(keyword: str) -> None:
    with pytest.raises(HTTPException) as exc:
        _block_mutating_sql(f"please {keyword.lower()} from users")

    assert exc.value.status_code == 400


def test_readonly_tables_include_document_related_tables() -> None:
    assert REQUIRED_TABLES.issubset(set(_READONLY_TABLES))


def test_run_nl_to_sql_agent_handles_output_parsing_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingAgent:
        def invoke(self, *_args, **_kwargs):
            raise ValueError("Could not parse LLM output: I don't know")

    monkeypatch.setattr(nl_to_sql_chain, "create_sql_agent", lambda *args, **kwargs: _FailingAgent())

    result = nl_to_sql_chain.run_nl_to_sql_agent("what is my database name?", "user@amzur.com")

    assert result["question"] == "what is my database name?"
    assert result["sql"] == ""
    assert "could not determine a reliable sql answer" in result["answer"].lower()
