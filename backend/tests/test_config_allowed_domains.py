from app.core.config import Settings


def _base_kwargs() -> dict[str, str]:
    return {
        "SECRET_KEY": "test-secret",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb",
        "LITELLM_API_KEY": "test-key",
    }


def test_allowed_domains_defaults_include_both() -> None:
    settings = Settings(**_base_kwargs())
    assert settings.ALLOWED_DOMAINS == ["amzur.com", "evokesystems.com"]


def test_allowed_domains_accepts_csv_string() -> None:
    settings = Settings(
        **_base_kwargs(),
        ALLOWED_DOMAINS="amzur.com, evokesystems.com",
    )
    assert settings.ALLOWED_DOMAINS == ["amzur.com", "evokesystems.com"]


def test_allowed_domains_accepts_json_list() -> None:
    settings = Settings(
        **_base_kwargs(),
        ALLOWED_DOMAINS=["amzur.com", "evokesystems.com"],
    )
    assert settings.ALLOWED_DOMAINS == ["amzur.com", "evokesystems.com"]
