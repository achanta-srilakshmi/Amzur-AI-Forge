from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.core.config import settings


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None

    @field_validator("email")
    @classmethod
    def enforce_domain(cls, v: str) -> str:
        email = v.lower()
        if not any(email.endswith(f"@{d}") for d in settings.ALLOWED_DOMAINS):
            domains = " or ".join(f"@{d}" for d in settings.ALLOWED_DOMAINS)
            raise ValueError(f"Only {domains} email addresses are allowed")
        return email

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def enforce_domain(cls, v: str) -> str:
        email = v.lower()
        if not any(email.endswith(f"@{d}") for d in settings.ALLOWED_DOMAINS):
            domains = " or ".join(f"@{d}" for d in settings.ALLOWED_DOMAINS)
            raise ValueError(f"Only {domains} email addresses are allowed")
        return email


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    avatar_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str:
        return str(v)
