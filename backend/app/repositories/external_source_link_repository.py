import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_source_link import ExternalSourceLink


async def save_external_source_links(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    links: list[tuple[str, str]],
) -> list[ExternalSourceLink]:
    persisted: list[ExternalSourceLink] = []

    for source_kind, url in links:
        result = await db.execute(
            select(ExternalSourceLink).where(
                (ExternalSourceLink.user_id == user_id)
                & (ExternalSourceLink.url == url)
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.source_kind = source_kind
            existing.updated_at = datetime.now(timezone.utc)
            persisted.append(existing)
            continue

        record = ExternalSourceLink(
            id=uuid.uuid4(),
            user_id=user_id,
            source_kind=source_kind,
            url=url,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(record)
        persisted.append(record)

    if links:
        await db.commit()

    return persisted