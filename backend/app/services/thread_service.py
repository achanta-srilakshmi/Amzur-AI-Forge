"""Thread CRUD service."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thread import Thread
from app.models.user import User
from app.schemas.thread import ThreadCreate, ThreadUpdate


async def create_thread(data: ThreadCreate, user: User, db: AsyncSession) -> Thread:
    thread = Thread(
        id=uuid.uuid4(),
        user_id=user.id,
        title=data.title or "New Chat",
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return thread


async def list_threads(user: User, db: AsyncSession) -> list[Thread]:
    result = await db.execute(
        select(Thread)
        .where(Thread.user_id == user.id)
        .order_by(Thread.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_thread(thread_id: str, user: User, db: AsyncSession) -> Thread:
    result = await db.execute(
        select(Thread).where(Thread.id == uuid.UUID(thread_id), Thread.user_id == user.id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Thread not found"},
        )
    return thread


async def update_thread(thread_id: str, data: ThreadUpdate, user: User, db: AsyncSession) -> Thread:
    thread = await get_thread(thread_id, user, db)
    thread.title = data.title
    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(thread)
    return thread


async def delete_thread(thread_id: str, user: User, db: AsyncSession) -> None:
    thread = await get_thread(thread_id, user, db)
    await db.delete(thread)
    await db.commit()
