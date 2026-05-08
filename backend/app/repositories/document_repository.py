"""Repository for Document metadata persistence."""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


async def create_document(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    filename: str,
    file_path: str,
    file_hash: str,
    chunk_count: int = 0,
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        user_id=user_id,
        thread_id=thread_id,
        filename=filename,
        file_path=file_path,
        file_hash=file_hash,
        chunk_count=chunk_count,
    )
    db.add(doc)
    await db.commit()
    return doc


async def update_document_chunk_count(
    db: AsyncSession,
    document_id: uuid.UUID,
    chunk_count: int,
) -> None:
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if doc:
        doc.chunk_count = chunk_count
        await db.commit()


async def get_document_by_hash_and_user(
    db: AsyncSession,
    file_hash: str,
    user_id: uuid.UUID,
) -> Optional[Document]:
    result = await db.execute(
        select(Document).where(
            (Document.file_hash == file_hash) & (Document.user_id == user_id)
        ).order_by(Document.created_at.desc())
    )
    return result.scalars().first()


async def list_documents_for_thread(
    db: AsyncSession,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(
            (Document.thread_id == thread_id) & (Document.user_id == user_id)
        )
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def thread_has_documents(
    db: AsyncSession,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    docs = await list_documents_for_thread(db, thread_id, user_id)
    return len(docs) > 0
