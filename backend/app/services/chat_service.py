"""
Chat service — saves messages and streams LLM responses.
"""
import base64
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from langchain_core.messages import HumanMessage
from openai import OpenAIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chains.chat_chain import chat_chain  # type: ignore[reportUnknownVariableType]
from app.ai.llm import llm
from app.ai.memory.conversation import thread_memory
from app.models.attachment import Attachment
from app.models.message import Message, MessageRole
from app.models.thread import Thread
from app.models.user import User
from app.repositories.generated_image_repository import (
    create_generated_image,
    link_generated_image_to_message,
)
from app.services.attachment_service import bind_attachments_to_message, build_attachment_context
from app.services.image_service import generate_image_for_prompt
from app.services.rag_service import retrieve_context
from app.repositories.document_repository import thread_has_documents
from app.services.thread_service import get_thread
from app.services.image_processing_service import ImageProcessingService
from app.services.intent_service import (
    detect_image_generation_intent,
    detect_image_modification_intent,
    extract_modification_params,
)
from app.services.text_to_sql_service import (
    SqlSafetyError,
    build_text_to_sql_stream_tail,
    detect_database_query_intent,
    run_text_to_sql,
)
from app.repositories.external_source_link_repository import save_external_source_links
from app.services.external_source_link_service import extract_shared_source_links
from app.core.config import settings
from app.models.generated_image import GeneratedImage

logger = logging.getLogger(__name__)

_MAX_TITLE_LEN = 60
_TITLE_PROMPT = (
    "Generate a concise 3-6 word title for a chat conversation that begins "
    "with the following message. Return only the title — no quotes, no punctuation at the end:\n\n"
)


async def _generate_title(user_message: str, user_email: str) -> str:
    """Ask the LLM for a short title; fall back to truncation on any error."""
    try:
        result = await llm.ainvoke(
            [HumanMessage(content=f"{_TITLE_PROMPT}{user_message[:300]}")],
            config={"metadata": {"user_email": user_email}},
        )
        raw_content = cast(object, result.content)  # type: ignore[reportUnknownMemberType]
        if isinstance(raw_content, list):
            normalized = " ".join(str(item) for item in cast(list[object], raw_content))
        else:
            normalized = str(raw_content)
        title = normalized.strip().strip('"').strip("'")
        return title[:_MAX_TITLE_LEN] or user_message[:_MAX_TITLE_LEN]
    except Exception:
        return user_message[:_MAX_TITLE_LEN]


async def _save_message(
    db: AsyncSession,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MessageRole,
    content: str,
) -> Message:
    msg = Message(
        id=uuid.uuid4(),
        thread_id=thread_id,
        user_id=user_id,
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(msg)
    await db.commit()
    return msg


async def _get_recent_generated_images(
    db: AsyncSession,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 5,
) -> list[GeneratedImage]:
    """Extract recent generated images from thread message history.
    
    Args:
        db: Database session
        thread_id: Thread ID
        user_id: User ID (for ownership verification)
        limit: Number of messages to scan (default: 5)
    
    Returns:
        List of GeneratedImage objects found in recent messages
    """
    # Get recent messages from this thread
    result = await db.execute(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    recent_messages = list(result.scalars().all())
    logger.info(f"[DEBUG] Scanning {len(recent_messages)} recent messages for generated images")
    
    generated_images = []
    image_id_pattern = re.compile(r"/api/threads/[^/]+/generated-images/([a-f0-9\-]+)")
    
    for i, message in enumerate(recent_messages):
        logger.info(f"[DEBUG] Message {i}: role={message.role}, content_len={len(message.content)}")
        logger.debug(f"[DEBUG] Message content preview: {message.content[:200]}")
        
        # Find all generated image IDs in message content
        matches = image_id_pattern.findall(message.content)
        logger.info(f"[DEBUG] Found {len(matches)} image ID(s) in message: {matches}")
        
        for image_id_str in matches:
            try:
                image_id = uuid.UUID(image_id_str)
                logger.info(f"[DEBUG] Parsed UUID: {image_id}")
                
                # Fetch the GeneratedImage
                img_result = await db.execute(
                    select(GeneratedImage)
                    .where(
                        (GeneratedImage.id == image_id) &
                        (GeneratedImage.thread_id == thread_id) &
                        (GeneratedImage.user_id == user_id)
                    )
                )
                generated_image = img_result.scalar_one_or_none()
                logger.info(f"[DEBUG] Query result for {image_id}: {generated_image}")
                
                if generated_image and generated_image not in generated_images:
                    logger.info(f"[DEBUG] Added image to list: {generated_image.id}")
                    generated_images.append(generated_image)
            except (ValueError, Exception) as e:
                logger.warning(f"[DEBUG] Failed to parse image ID {image_id_str}: {e}")
    
    logger.info(f"[DEBUG] Returning {len(generated_images)} generated image(s)")
    return generated_images


async def _message_count(thread_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).where(Message.thread_id == thread_id)
    )
    return result.scalar_one()


async def stream_chat_response(
    user_message: str,
    thread: Thread,
    user: User,
    db: AsyncSession,
    attachments: list[Attachment] | None = None,
    interaction_mode: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    1. Auto-title thread from first user message (if still default).
    2. Persist user message.
    3. Stream LLM reply token-by-token.
    4. Persist full assistant response after streaming completes.
    """
    logger.info(
        f"stream_chat_response called with {len(attachments or [])} attachments "
        f"for thread {thread.id}, user {user.email}"
    )
    
    # Auto-title: generate a meaningful title from the first user message
    msg_count = await _message_count(thread.id, db)
    if msg_count == 0 and thread.title in ("New Chat", "New conversation"):
        thread.title = await _generate_title(user_message, user.email)

    attachment_context = await build_attachment_context(
        attachments or [], user.email, db
    )
    logger.info(f"Attachment context length: {len(attachment_context)} chars")
    if attachment_context:
        logger.debug(f"Attachment context preview: {attachment_context[:200]}")
    
    enriched_input = user_message
    if attachment_context:
        enriched_input = (
            f"{user_message}\n\nAttached context:\n{attachment_context}"
        )
        logger.info(
            f"Enriched input with attachment context. Total input length: {len(enriched_input)}"
        )

    # Persist user message and bump updated_at
    links_to_persist = extract_shared_source_links(user_message)
    if links_to_persist:
        try:
            await save_external_source_links(
                db,
                user_id=user.id,
                links=links_to_persist,
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist external source links for user %s: %s",
                user.email,
                exc,
            )

    saved_user_message = await _save_message(
        db, thread.id, user.id, MessageRole.user, user_message
    )
    if attachments:
        await bind_attachments_to_message(attachments, saved_user_message, db)

    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(f"[DEBUG] === CHECKING IMAGE GENERATION INTENT ===")
    force_generate = interaction_mode == "generate"
    force_database = interaction_mode == "database"

    if user_message.strip() and (force_generate or await detect_image_generation_intent(user_message, user.email)):
        logger.info(f"[DEBUG] IMAGE GENERATION INTENT MATCHED - generating image")
        try:
            generated_image = await generate_image_for_prompt(
                db=db,
                thread_id=thread.id,
                user_id=user.id,
                user_email=user.email,
                prompt=user_message,
            )
            image_path = f"/api/threads/{thread.id}/generated-images/{generated_image.id}"

            # Persist an internal retrievable path when provider URL is unavailable.
            if not generated_image.image_url:
                generated_image.image_url = image_path
                await db.commit()

            assistant_response = (
                f"Generated image for your prompt:\n\n"
                f"![Generated image]({image_path})"
            )
            saved_assistant_message = await _save_message(
                db, thread.id, user.id, MessageRole.assistant, assistant_response
            )
            await link_generated_image_to_message(
                db,
                generated_image=generated_image,
                message_id=saved_assistant_message.id,
            )
            thread.updated_at = datetime.now(timezone.utc)
            await db.commit()

            async def _image_generate() -> AsyncGenerator[str, None]:
                yield assistant_response

            return _image_generate()
        except Exception as exc:
            # Graceful fallback: keep legacy text path if image generation fails.
            logger.warning(
                "Image generation failed for thread %s, falling back to text response: %s",
                thread.id,
                exc,
            )
            try:
                await db.rollback()
            except Exception as rollback_exc:
                logger.error(
                    "Failed to rollback transaction after image generation failure for thread %s: %s",
                    thread.id,
                    rollback_exc,
                    exc_info=True,
                )

    logger.info(f"[DEBUG] === CHECKING IMAGE MODIFICATION INTENT ===")
    # Check for image modification intent if attachments contain images
    is_modification, operation = detect_image_modification_intent(user_message)
    logger.info(f"[DEBUG] Modification detection result: is_modification={is_modification}, operation={operation}")
    
    if is_modification:
        try:
            # Find the image to modify - check current attachments first
            image_attachment = None
            image_base64 = None
            
            logger.info(f"[DEBUG] Checking for image: current_attachments={len(attachments or [])}")
            
            if attachments:
                for att in attachments:
                    if att.mime_type and att.mime_type.startswith("image/"):
                        image_attachment = att
                        break
                
                if image_attachment and image_attachment.file_path:
                    logger.info(f"[DEBUG] Found current image attachment: {image_attachment.file_path}")
                    image_file_path = Path(settings.UPLOAD_DIR) / image_attachment.file_path
                    if image_file_path.exists():
                        with open(image_file_path, "rb") as f:
                            image_base64 = base64.b64encode(f.read()).decode()
                        logger.info(f"[DEBUG] Loaded current attachment as base64")
            
            # If no current attachment, check recent generated images from thread history
            if not image_base64:
                logger.info(f"[DEBUG] No current attachment, checking thread history...")
                recent_generated_images = await _get_recent_generated_images(
                    db, thread.id, user.id, limit=5
                )
                logger.info(f"[DEBUG] Found {len(recent_generated_images)} recent generated image(s)")
                
                if recent_generated_images:
                    latest_image = recent_generated_images[0]  # Most recent
                    logger.info(f"[DEBUG] Using recent generated image: {latest_image.id}")
                    
                    # Try to load from storage_path first
                    if latest_image.storage_path:
                        try:
                            image_file_path = Path(settings.UPLOAD_DIR) / latest_image.storage_path
                            logger.info(f"[DEBUG] Trying to load from storage_path: {image_file_path}")
                            if image_file_path.exists():
                                with open(image_file_path, "rb") as f:
                                    image_base64 = base64.b64encode(f.read()).decode()
                                logger.info(f"[DEBUG] Successfully loaded image from storage_path")
                        except Exception as e:
                            logger.warning(f"[DEBUG] Failed to load image from storage_path: {e}")
                    
                    # Fallback to image_base64 from DB if storage_path doesn't work
                    if not image_base64 and latest_image.image_base64:
                        logger.info(f"[DEBUG] Using image_base64 from database")
                        image_base64 = latest_image.image_base64
            
            logger.info(f"[DEBUG] Final image_base64 available: {image_base64 is not None}")
            
            if image_base64:
                # Extract modification parameters
                params = await extract_modification_params(user_message, operation, user.email)
                
                # Process the image
                logger.info(f"Processing image modification: {operation}")
                logger.info(f"[DEBUG] Modification params: {params}")
                modified_base64 = None
                result_message = ""
                
                try:
                    if operation == "color_change":
                        modified_base64 = await ImageProcessingService.change_object_color(
                            image_base64,
                            params.get("object_description", ""),
                            tuple(params.get("target_color", (255, 255, 255))),
                            params.get("tolerance", 30),
                        )
                        result_message = f"Successfully changed the color of the {params.get('object_description', 'object')} to {params.get('target_color', 'white')}."
                    
                    elif operation == "brightness":
                        modified_base64 = await ImageProcessingService.adjust_brightness(
                            image_base64,
                            params.get("factor", 1.0),
                        )
                        factor = params.get("factor", 1.0)
                        direction = "brightened" if factor > 1.0 else "darkened"
                        result_message = f"Successfully {direction} the image."
                    
                    elif operation == "contrast":
                        modified_base64 = await ImageProcessingService.adjust_contrast(
                            image_base64,
                            params.get("factor", 1.0),
                        )
                        factor = params.get("factor", 1.0)
                        direction = "increased" if factor > 1.0 else "decreased"
                        result_message = f"Successfully {direction} the image contrast."
                    
                    elif operation == "analyze":
                        analysis = await ImageProcessingService.analyze_image_content(image_base64)
                        result_message = f"Image Analysis:\n- Size: {analysis['width']}x{analysis['height']} pixels\n- Format: {analysis['format']}\n- Mode: {analysis['mode']}\n- Dominant Color: RGB{analysis['dominant_color']}"
                
                except Exception as process_exc:
                    logger.error(f"[DEBUG] Image processing failed: {process_exc}", exc_info=True)
                    raise
                
                # Save the user message
                saved_user_message = await _save_message(
                    db, thread.id, user.id, MessageRole.user, user_message
                )
                if attachments:
                    await bind_attachments_to_message(attachments, saved_user_message, db)
                
                # If modified image exists, create response with it
                if modified_base64:
                    # Save the modified image as a generated_image record
                    modified_image_record = await create_generated_image(
                        db,
                        thread_id=thread.id,
                        user_id=user.id,
                        message_id=None,
                        prompt=f"{operation} modification of: {user_message}",
                        storage_path=None,
                        image_base64=modified_base64,
                        image_url=None,
                        mime_type="image/png",
                        provider_model="local-modification",
                    )
                    
                    # Create response with the modified image using correct endpoint
                    modified_image_path = f"/api/threads/{thread.id}/generated-images/{modified_image_record.id}"
                    modified_image_markdown = f"![Modified image]({modified_image_path})"
                    assistant_response = f"{result_message}\n\n{modified_image_markdown}"
                else:
                    assistant_response = result_message
                
                # Save assistant message
                saved_assistant_message = await _save_message(
                    db, thread.id, user.id, MessageRole.assistant, assistant_response
                )
                
                thread.updated_at = datetime.now(timezone.utc)
                await db.commit()
                
                async def _image_modify() -> AsyncGenerator[str, None]:
                    yield assistant_response
                
                logger.info(f"[DEBUG] Image modification completed successfully, returning response")
                return _image_modify()
            else:
                logger.warning(f"[DEBUG] No image found to modify (neither in current attachments nor recent history)")
        except Exception as exc:
            logger.error(
                f"[DEBUG] Image modification failed: {type(exc).__name__}: {str(exc)}",
                exc_info=True,
            )
            logger.warning(
                "Image modification failed for thread %s, falling back to text response: %s",
                thread.id,
                exc,
            )
            try:
                await db.rollback()
            except Exception as rollback_exc:
                logger.error(
                    "Failed to rollback after image modification failure: %s",
                    rollback_exc,
                    exc_info=True,
                )
            # After rollback, we need to refresh the thread object to maintain session context
            thread = await get_thread(thread.id, user, db)

    logger.info("[DEBUG] === NO IMAGE MODIFICATION DETECTED - PROCEEDING TO LLM RESPONSE ===")

    if user_message.strip() and (force_database or await detect_database_query_intent(user_message, user.email)):
        logger.info("[TEXT2SQL] Database intent detected. Executing Text-to-SQL path.")
        try:
            sql_result = await run_text_to_sql(user_message, user.email)
            assistant_response = sql_result.response_text

            await _save_message(
                db, thread.id, user.id, MessageRole.assistant, assistant_response
            )
            thread.updated_at = datetime.now(timezone.utc)
            await db.commit()

            async def _sql_generate() -> AsyncGenerator[str, None]:
                yield assistant_response
                yield build_text_to_sql_stream_tail(sql_result)

            return _sql_generate()
        except SqlSafetyError as exc:
            logger.warning("[TEXT2SQL] Rejected unsafe SQL for thread %s: %s", thread.id, exc)
            assistant_response = (
                "I could not run that database query safely. "
                "Please rephrase as a read-only question."
            )
            await _save_message(
                db, thread.id, user.id, MessageRole.assistant, assistant_response
            )
            thread.updated_at = datetime.now(timezone.utc)
            await db.commit()

            async def _sql_rejected() -> AsyncGenerator[str, None]:
                yield assistant_response

            return _sql_rejected()
        except Exception as exc:
            logger.error("[TEXT2SQL] Failed to execute SQL flow for thread %s: %s", thread.id, exc, exc_info=True)
            assistant_response = (
                "I could not complete the database query right now. "
                "Please try again in a moment."
            )
            await _save_message(
                db, thread.id, user.id, MessageRole.assistant, assistant_response
            )
            thread.updated_at = datetime.now(timezone.utc)
            await db.commit()

            async def _sql_error() -> AsyncGenerator[str, None]:
                yield assistant_response

            return _sql_error()

    # RAG: check if this thread has any uploaded documents and retrieve relevant context
    rag_context: str | None = None
    if await thread_has_documents(db, thread.id, user.id):
        logger.info("[RAG] Thread has documents — querying ChromaDB for relevant context")
        rag_context = await retrieve_context(
            query=user_message,
            user_id=user.id,
            thread_id=thread.id,
            user_email=user.email,
        )
        if rag_context:
            logger.info("[RAG] Context retrieved (%d chars) — injecting into prompt", len(rag_context))
        else:
            logger.info("[RAG] No relevant context found — falling back to normal LLM path")

    # Build final input: attachment context + RAG context + user message
    final_input = enriched_input
    if rag_context:
        final_input = (
            f"{user_message}\n\n"
            f"Use the following document context to answer the question. "
            f"If the answer is not in the context, say so clearly.\n\n"
            f"--- Document Context ---\n{rag_context}\n--- End Context ---"
        )
        if attachment_context:
            final_input = (
                f"{user_message}\n\nAttached context:\n{attachment_context}\n\n"
                f"Use the following document context to answer the question. "
                f"If the answer is not in the context, say so clearly.\n\n"
                f"--- Document Context ---\n{rag_context}\n--- End Context ---"
            )

    # Load history excluding the message just saved
    history = await thread_memory.load(thread.id, db)

    full_response: list[str] = []

    async def _generate() -> AsyncGenerator[str, None]:
        try:
            stream_iter = cast(
                AsyncGenerator[str, None],
                chat_chain.astream(  # type: ignore[reportUnknownMemberType]
                    {"human_input": final_input, "history": history},
                    config={"metadata": {"user_email": user.email}},
                ),
            )
            async for chunk in stream_iter:
                full_response.append(chunk)
                yield chunk
        except OpenAIError as exc:
            yield f"\n\n[Error communicating with the AI: {exc}]"
        except Exception as exc:
            yield f"\n\n[Unexpected error while generating response: {exc}]"
        finally:
            assembled = "".join(full_response)
            if assembled:
                await _save_message(
                    db, thread.id, user.id, MessageRole.assistant, assembled
                )
                thread.updated_at = datetime.now(timezone.utc)
                await db.commit()

    return _generate()


async def list_messages(thread_id: str, db: AsyncSession) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.thread_id == uuid.UUID(thread_id))
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())
