"""Auth routes -- register, login, logout, me, Google OAuth."""
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.services.auth_service import (
    get_current_user,
    handle_google_callback,
    login_user,
    logout_user,
    register_user,
)

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(
    data: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    return await register_user(data, db, response)


@router.post("/login", response_model=UserResponse)
async def login(
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    return await login_user(data, db, response)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    logout_user(response)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


# -- Google OAuth -------------------------------------------------------------


@router.get("/google")
async def google_login() -> RedirectResponse:
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_callback(
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    redirect_url = await handle_google_callback(code, db, response)
    return RedirectResponse(url=redirect_url)