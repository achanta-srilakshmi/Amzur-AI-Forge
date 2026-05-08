import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generated_image import GeneratedImage


async def create_generated_image(
    db: AsyncSession,
    *,
    generated_id: uuid.UUID | None = None,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    message_id: uuid.UUID | None,
    prompt: str,
    storage_path: str | None,
    image_base64: str | None,
    image_url: str | None,
    mime_type: str,
    provider_model: str,
) -> GeneratedImage:
    generated = GeneratedImage(
        id=generated_id or uuid.uuid4(),
        thread_id=thread_id,
        user_id=user_id,
        message_id=message_id,
        prompt=prompt,
        storage_path=storage_path,
        image_base64=image_base64,
        image_url=image_url,
        mime_type=mime_type,
        provider_model=provider_model,
    )
    db.add(generated)
    await db.commit()
    await db.refresh(generated)
    return generated


async def get_generated_image_for_user_thread(
    db: AsyncSession,
    *,
    image_id: uuid.UUID,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
) -> GeneratedImage | None:
    result = await db.execute(
        select(GeneratedImage).where(
            (GeneratedImage.id == image_id) &
            (GeneratedImage.thread_id == thread_id) &
            (GeneratedImage.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def link_generated_image_to_message(
    db: AsyncSession,
    *,
    generated_image: GeneratedImage,
    message_id: uuid.UUID,
) -> GeneratedImage:
    generated_image.message_id = message_id
    await db.commit()
    await db.refresh(generated_image)
    return generated_image
