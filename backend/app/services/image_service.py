import logging
import base64
import uuid
from pathlib import Path
from typing import Any, cast

from openai import OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import openai_client
from app.core.config import settings
from app.models.generated_image import GeneratedImage
from app.repositories.generated_image_repository import create_generated_image

logger = logging.getLogger(__name__)


def _save_generated_image_to_disk(
    *,
    image_id: uuid.UUID,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    image_b64: str,
) -> str:
    payload = image_b64
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]

    image_bytes = base64.b64decode(payload, validate=True)
    upload_root = Path(settings.UPLOAD_DIR)
    relative_path = Path("generated-images") / str(user_id) / str(thread_id) / f"{image_id}.png"
    absolute_path = upload_root / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(image_bytes)
    return relative_path.as_posix()


def _extract_first_image_payload(response: object) -> tuple[str | None, str | None, str]:
    data_attr = getattr(response, "data", None)
    if not isinstance(data_attr, list) or len(data_attr) == 0:
        raise ValueError("Image generation response did not include data")

    first_item = data_attr[0]
    b64_json = getattr(first_item, "b64_json", None)
    image_url = getattr(first_item, "url", None)

    # Some providers may return dict-like payloads.
    if b64_json is None and isinstance(first_item, dict):
        b64_json = first_item.get("b64_json")
    if image_url is None and isinstance(first_item, dict):
        image_url = first_item.get("url")

    revised_prompt = getattr(first_item, "revised_prompt", "")
    if isinstance(first_item, dict) and not revised_prompt:
        revised_prompt = first_item.get("revised_prompt", "")

    if b64_json is None and image_url is None:
        raise ValueError("Image generation returned neither base64 nor URL")

    return (
        cast(str | None, b64_json),
        cast(str | None, image_url),
        cast(str, revised_prompt) if isinstance(revised_prompt, str) else "",
    )


async def generate_image_for_prompt(
    *,
    db: AsyncSession,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    user_email: str,
    prompt: str,
) -> GeneratedImage:
    logger.info("Generating image for thread=%s user=%s", thread_id, user_email)
    try:
        response = openai_client.images.generate(
            model=settings.IMAGE_GEN_MODEL,
            prompt=prompt,
            user=user_email,
            extra_body={
                "metadata": {
                    "application": settings.APP_NAME,
                    "environment": settings.ENVIRONMENT,
                }
            },
        )
        image_b64, image_url, revised_prompt = _extract_first_image_payload(response)
        persisted_prompt = revised_prompt or prompt

        generated_id = uuid.uuid4()
        storage_path: str | None = None
        stored_image_b64: str | None = image_b64

        if image_b64:
            storage_path = _save_generated_image_to_disk(
                image_id=generated_id,
                user_id=user_id,
                thread_id=thread_id,
                image_b64=image_b64,
            )
            # Persist file path as canonical storage and avoid bloating DB rows.
            stored_image_b64 = None

        return await create_generated_image(
            db,
            generated_id=generated_id,
            thread_id=thread_id,
            user_id=user_id,
            message_id=None,
            prompt=persisted_prompt,
            storage_path=storage_path,
            image_base64=stored_image_b64,
            image_url=image_url,
            mime_type="image/png",
            provider_model=settings.IMAGE_GEN_MODEL,
        )
    except OpenAIError:
        logger.exception("Image generation failed with OpenAI/LiteLLM error")
        raise
    except Exception:
        logger.exception("Image generation failed with unexpected error")
        raise
