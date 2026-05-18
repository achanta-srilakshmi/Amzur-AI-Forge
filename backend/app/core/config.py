from typing import Any, List, Optional

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "amzur-ai-chat"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str
    JWT_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # Database
    DATABASE_URL: str  # postgresql[+asyncpg]://...

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Ensure the URL uses the asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Synchronous psycopg2 URL for tools that require it (e.g. Alembic, LangChain SQL agent)."""
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            return url
        return url

    # Amzur LiteLLM Proxy
    LITELLM_PROXY_URL: str = "https://litellm.amzur.com"
    LITELLM_API_KEY: str
    LLM_MODEL: str = "gemini/gemini-2.5-flash"
    LITELLM_EMBEDDING_MODEL: str = "text-embedding-3-large"
    IMAGE_GEN_MODEL: str = "gemini/imagen-4.0-fast-generate-001"

    # Domain restriction (applies to both email/password and Google OAuth)
    # Accepts a JSON array or comma-separated string: ALLOWED_DOMAINS=["amzur.com","evokesystems.com"]
    ALLOWED_DOMAINS: List[str] = ["amzur.com", "evokesystems.com"]

    @field_validator("ALLOWED_DOMAINS", mode="before")
    @classmethod
    def parse_allowed_domains(cls, value: Any) -> Any:
        """Accept JSON arrays or comma-separated strings for ALLOWED_DOMAINS."""
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                return value
            return [
                item.strip()
                for item in raw.split(",")
                if item.strip()
            ]
        return value

    @field_validator("RESEARCH_MCP_ARGS", mode="before")
    @classmethod
    def parse_research_mcp_args(cls, value: Any) -> Any:
        """Accept JSON arrays or comma-separated strings for RESEARCH_MCP_ARGS."""
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                return value
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    # Frontend origin — used for OAuth redirects
    FRONTEND_URL: str = "http://localhost:5173"

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Research MCP
    RESEARCH_MCP_TRANSPORT: str = "sse"
    RESEARCH_MCP_URL: Optional[str] = "https://mcp.arxiv.org/sse"
    RESEARCH_MCP_COMMAND: Optional[str] = None
    RESEARCH_MCP_ARGS: List[str] = []

    # Google Sheets
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = None

    # File uploads
    MAX_UPLOAD_MB: int = 20
    UPLOAD_DIR: str = "./uploads"
    ACCEPTED_MIME_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/heic",
        "image/heif",
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/plain",
        "text/csv",
        "application/json",
        "text/markdown",
        "application/xml",
        "text/xml",
        "text/x-python",
        "text/javascript",
        "application/javascript",
        "text/x-java-source",
        "text/x-tex",
        "application/x-tex",
    ]


settings = Settings()
