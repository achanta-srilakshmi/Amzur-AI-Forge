#!/usr/bin/env python3
"""
Backfill script for generated_images table.

Populates storage_path and message_id for older records that were created before
the disk storage and message linkage implementation.

Usage:
    cd backend
    python scripts/backfill_generated_images.py
"""
import asyncio
import base64
import logging
import sys
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.generated_image import GeneratedImage
from app.models.message import Message, MessageRole

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def backfill_generated_images() -> None:
    """Backfill storage_path and message_id for older generated_images records."""
    
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as db:
            # Find all records with NULL storage_path
            result = await db.execute(
                select(GeneratedImage).where(GeneratedImage.storage_path == None)
            )
            records = list(result.scalars().all())
            
            if not records:
                logger.info("No records to backfill. All generated_images have storage_path set.")
                return
            
            logger.info(f"Found {len(records)} record(s) to backfill.")
            upload_root = Path(settings.UPLOAD_DIR)
            
            for idx, record in enumerate(records, start=1):
                logger.info(f"[{idx}/{len(records)}] Processing generated_image {record.id}")
                
                # Step 1: Save base64 to disk if available
                if record.image_base64:
                    try:
                        storage_path = _save_image_to_disk(
                            upload_root,
                            record.id,
                            record.user_id,
                            record.thread_id,
                            record.image_base64,
                        )
                        record.storage_path = storage_path
                        record.image_base64 = None  # Clear from DB to save space
                        logger.info(f"  ✓ Saved to disk: {storage_path}")
                    except Exception as exc:
                        logger.error(f"  ✗ Failed to save to disk: {exc}")
                        continue
                elif record.image_url:
                    # Has provider URL but no base64 — nothing to migrate
                    logger.info(f"  ~ Has provider URL only, skipping disk storage")
                else:
                    logger.warning(f"  ! No image_base64 or image_url, skipping")
                    continue
                
                # Step 2: Link to corresponding message if not already linked
                if not record.message_id:
                    try:
                        message_id = await _find_corresponding_message(
                            db, record.thread_id, record.created_at
                        )
                        if message_id:
                            record.message_id = message_id
                            logger.info(f"  ✓ Linked to message {message_id}")
                        else:
                            logger.info(f"  ~ No corresponding message found")
                    except Exception as exc:
                        logger.error(f"  ✗ Failed to link message: {exc}")
                
                # Commit this record
                try:
                    await db.commit()
                    logger.info(f"  ✓ Record updated and committed")
                except Exception as exc:
                    await db.rollback()
                    logger.error(f"  ✗ Failed to commit: {exc}")
            
            logger.info(f"✓ Backfill complete. {len(records)} record(s) processed.")
    
    finally:
        await engine.dispose()


def _save_image_to_disk(
    upload_root: Path,
    image_id: uuid.UUID,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    image_b64: str,
) -> str:
    """Decode base64 image and save to disk. Return relative storage_path."""
    
    payload = image_b64
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]
    
    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise ValueError(f"Failed to decode base64: {exc}") from exc
    
    relative_path = Path("generated-images") / str(user_id) / str(thread_id) / f"{image_id}.png"
    absolute_path = upload_root / relative_path
    
    # Create directory if needed
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if file already exists
    if absolute_path.exists():
        logger.debug(f"  File already exists at {relative_path}, skipping write")
        return relative_path.as_posix()
    
    # Write to disk
    absolute_path.write_bytes(image_bytes)
    
    if not absolute_path.exists():
        raise RuntimeError(f"Failed to write file to {absolute_path}")
    
    return relative_path.as_posix()


async def _find_corresponding_message(
    db: AsyncSession,
    thread_id: uuid.UUID,
    generated_at: object,
) -> uuid.UUID | None:
    """
    Find the assistant message that likely corresponds to this generated image.
    
    Strategy: Find the first assistant message in the thread that was created
    within 10 seconds after the generated_image record was created.
    """
    
    if not generated_at:
        return None
    
    # Convert to datetime if needed
    from datetime import datetime
    if not isinstance(generated_at, datetime):
        return None
    
    # Search for assistant messages in the same thread, created shortly after
    result = await db.execute(
        select(Message).where(
            Message.thread_id == thread_id,
            Message.role == MessageRole.assistant,
            Message.created_at >= generated_at,
            Message.created_at <= generated_at + timedelta(seconds=10),
        ).order_by(Message.created_at.asc()).limit(1)
    )
    
    message = result.scalar_one_or_none()
    return message.id if message else None


async def main() -> int:
    """Entry point."""
    try:
        logger.info("Starting backfill of generated_images...")
        await backfill_generated_images()
        logger.info("✓ Backfill completed successfully.")
        return 0
    except Exception as exc:
        logger.error(f"✗ Backfill failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
