"""
Auth service — registration, login, JWT cookie management, get_current_user, and Google OAuth.
"""
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Cookie, Depends, HTTPException, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def _create_jwt(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "development",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )


# ── Auth operations ───────────────────────────────────────────────────────────


async def register_user(
    data: RegisterRequest,
    db: AsyncSession,
    response: Response,
) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "conflict", "message": "Email already registered"},
        )

    user = User(
        id=uuid.uuid4(),
        email=data.email,
        display_name=data.display_name,
        hashed_password=_hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = _create_jwt(str(user.id))
    _set_auth_cookie(response, token)
    return user


async def login_user(
    data: LoginRequest,
    db: AsyncSession,
    response: Response,
) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not _verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid email or password"},
        )

    token = _create_jwt(str(user.id))
    _set_auth_cookie(response, token)
    return user


def logout_user(response: Response) -> None:
    response.delete_cookie("access_token")


# ── Dependency ────────────────────────────────────────────────────────────────


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "unauthorized", "message": "Not authenticated"},
    )

    if not access_token:
        raise credentials_exc

    try:
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exc

    return user


# ── Google OAuth ──────────────────────────────────────────────────────────────


async def handle_google_callback(
    code: str,
    db: AsyncSession,
    response: Response,
) -> str:
    """
    Exchange the Google authorisation code for tokens, resolve the user account,
    set the JWT cookie on *response*, and return the frontend redirect URL.

    Returns a redirect URL — either the app root or an error URL.
    """
    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()

            profile_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "oauth_error", "message": f"Google OAuth failed: {exc}"},
        )

    google_id: str = profile["sub"]
    email: str = profile["email"].lower()
    display_name: str | None = profile.get("name")
    avatar_url: str | None = profile.get("picture")

    # Domain restriction — same policy as email/password auth
    if not email.endswith(f"@{settings.ALLOWED_DOMAIN}"):
        from urllib.parse import quote_plus
        msg = quote_plus(f"Only @{settings.ALLOWED_DOMAIN} accounts are permitted")
        return f"{settings.FRONTEND_URL}?error={msg}"

    # Find or create user — link by email to avoid duplicates (AD-03)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        if not user.google_id:
            user.google_id = google_id
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url
        await db.commit()
    else:
        user = User(
            id=uuid.uuid4(),
            email=email,
            display_name=display_name,
            google_id=google_id,
            avatar_url=avatar_url,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    _set_auth_cookie(response, _create_jwt(str(user.id)))
    return settings.FRONTEND_URL

