"""Thread routes — CRUD for chat threads."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.thread import ThreadCreate, ThreadResponse, ThreadUpdate
from app.services.auth_service import get_current_user
from app.services.thread_service import (
    create_thread,
    delete_thread,
    get_thread,
    list_threads,
    update_thread,
)

router = APIRouter()


@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: ThreadCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    return await create_thread(data, current_user, db)


@router.get("", response_model=list[ThreadResponse])
async def list_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ThreadResponse]:
    return await list_threads(current_user, db)


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update(
    thread_id: str,
    data: ThreadUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    return await update_thread(thread_id, data, current_user, db)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_thread(thread_id, current_user, db)
