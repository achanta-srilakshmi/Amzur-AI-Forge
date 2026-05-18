"""Chat routes — message history and streaming LLM response."""
import base64
import logging
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from fastapi import File, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from starlette.datastructures import UploadFile as StarletteUploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.message import Message
from app.models.user import User
from app.schemas.attachment import AttachmentResponse
from app.schemas.message import MessageResponse
from app.services.auth_service import get_current_user
from app.services.attachment_service import (
    list_attachments_for_thread,
    load_attachments_for_thread,
    save_attachments,
)
from app.services.chat_service import list_messages, stream_chat_response
from app.services.image_processing_service import ImageProcessingService
from app.services.rag_service import ingest_document
from app.repositories.document_repository import list_documents_for_thread
from app.repositories.generated_image_repository import get_generated_image_for_user_thread
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.thread_service import get_thread
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
_ALLOWED_CHAT_MODES = {"pdf", "database", "generate", "chat"}


@router.get("/{thread_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Message]:
    await get_thread(thread_id, current_user, db)  # ownership check
    return await list_messages(thread_id, db)


@router.post("/{thread_id}/attachments", response_model=list[AttachmentResponse])
async def upload_attachments(
    thread_id: str,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Attachment]:
    thread = await get_thread(thread_id, current_user, db)
    return await save_attachments(thread, current_user, files, db)


@router.get("/{thread_id}/attachments", response_model=list[AttachmentResponse])
async def get_attachments(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Attachment]:
    thread = await get_thread(thread_id, current_user, db)
    return await list_attachments_for_thread(thread, current_user, db)


@router.get("/{thread_id}/generated-images/{image_id}")
async def get_generated_image(
    thread_id: str,
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    logger.info(f"[DEBUG] GET /generated-images/{image_id} called for thread {thread_id}")
    thread = await get_thread(thread_id, current_user, db)
    
    try:
        image_uuid = uuid.UUID(image_id)
        logger.info(f"[DEBUG] Parsed UUID: {image_uuid}")
    except ValueError as e:
        logger.error(f"[DEBUG] Invalid UUID: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_uuid", "message": "Invalid image ID format"},
        ) from e
    
    logger.info(f"[DEBUG] Querying for image: id={image_uuid}, thread={thread.id}, user={current_user.id}")
    generated_image = await get_generated_image_for_user_thread(
        db,
        image_id=image_uuid,
        thread_id=thread.id,
        user_id=current_user.id,
    )
    logger.info(f"[DEBUG] Query result: {generated_image}")
    
    if generated_image is None:
        logger.warning(f"[DEBUG] Generated image not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "generated_image_not_found",
                "message": "Generated image not found",
            },
        )

    logger.info(f"[DEBUG] Found image: storage_path={generated_image.storage_path}, has_base64={bool(generated_image.image_base64)}, image_url={generated_image.image_url}")
    
    if generated_image.storage_path:
        try:
            image_file = Path(settings.UPLOAD_DIR) / generated_image.storage_path
            logger.info(f"[DEBUG] Trying to load from storage_path: {image_file}")
            if image_file.exists() and image_file.is_file():
                logger.info(f"[DEBUG] File exists, returning image")
                return Response(
                    content=image_file.read_bytes(),
                    media_type=generated_image.mime_type,
                )
            logger.warning(f"[DEBUG] File does not exist: {image_file}")
        except Exception as exc:
            logger.error(
                "Failed to read generated image file %s: %s",
                generated_image.storage_path,
                exc,
                exc_info=True,
            )

    if generated_image.image_base64:
        try:
            logger.info(f"[DEBUG] Attempting to decode image_base64, length={len(generated_image.image_base64)}")
            payload = generated_image.image_base64
            if payload.startswith("data:") and "," in payload:
                payload = payload.split(",", 1)[1]
                logger.info(f"[DEBUG] Stripped data URI prefix, new length={len(payload)}")
            image_bytes = base64.b64decode(payload, validate=True)
            logger.info(f"[DEBUG] Successfully decoded image, bytes length={len(image_bytes)}")
            return Response(content=image_bytes, media_type=generated_image.mime_type)
        except Exception as exc:
            logger.error(
                "Failed to decode generated image %s: %s",
                generated_image.id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "generated_image_decode_failed",
                    "message": "Failed to decode generated image",
                },
            ) from exc

    if generated_image.image_url:
        logger.info(f"[DEBUG] Redirecting to image_url: {generated_image.image_url}")
        return RedirectResponse(url=generated_image.image_url)

    logger.warning(f"[DEBUG] No image payload available")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "generated_image_payload_missing",
            "message": "No image payload is available",
        },
    )


@router.post("/{thread_id}/chat")
async def chat(
    thread_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    logger.info(f"Chat endpoint called for thread {thread_id} by {current_user.email}")
    
    thread = await get_thread(thread_id, current_user, db)

    message = ""
    attachment_ids: str | None = None
    mode: str | None = None
    files: list[UploadFile | StarletteUploadFile] = []

    content_type = request.headers.get("content-type", "").lower()
    logger.info(f"Request content-type: {content_type}")
    
    if "multipart/form-data" in content_type:
        form = await request.form()
        message = str(form.get("message") or "")
        raw_attachment_ids = form.get("attachment_ids")
        attachment_ids = (
            str(raw_attachment_ids) if raw_attachment_ids is not None else None
        )
        raw_mode = form.get("mode")
        mode = str(raw_mode).strip().lower() if raw_mode is not None else None

        collected = [*form.getlist("files"), *form.getlist("files[]")]
        files = [
            item
            for item in collected
            if isinstance(item, (UploadFile, StarletteUploadFile))
        ]
        logger.info(
            f"Parsed multipart request: message_length={len(message)}, "
            f"attachment_ids={attachment_ids}, collected_count={len(collected)}, files_count={len(files)}"
        )
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        if isinstance(payload, dict):
            payload_map = cast(dict[str, Any], payload)
            raw_message = payload_map.get("message")
            message = str(raw_message or "")
            raw_attachment_ids = payload_map.get("attachment_ids")
            raw_mode = payload_map.get("mode")
            if raw_mode is not None:
                mode = str(raw_mode).strip().lower()
            if isinstance(raw_attachment_ids, Sequence) and not isinstance(
                raw_attachment_ids, str
            ):
                sequence_ids = cast(Sequence[object], raw_attachment_ids)
                attachment_ids = ",".join(str(item) for item in sequence_ids)
            elif raw_attachment_ids is not None:
                attachment_ids = str(raw_attachment_ids)
            logger.info(
                f"Parsed JSON request: message_length={len(message)}, "
                f"attachment_ids={attachment_ids}, mode={mode}"
            )

    if mode and mode not in _ALLOWED_CHAT_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "invalid_mode",
                "message": "mode must be one of: chat, pdf, database, generate",
            },
        )

    parsed_ids: list[uuid.UUID] = []
    if attachment_ids:
        try:
            parsed_ids = [
                uuid.UUID(raw.strip())
                for raw in attachment_ids.split(",")
                if raw.strip()
            ]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "invalid_attachment_ids",
                    "message": "attachment_ids must be comma-separated UUID values",
                },
            ) from exc

    logger.info(f"Loading {len(parsed_ids)} existing attachments...")
    existing_attachments = await load_attachments_for_thread(
        parsed_ids, thread, current_user, db
    )
    logger.info(f"Saving {len(files)} uploaded files...")
    uploaded_attachments = await save_attachments(
        thread, current_user, cast(list[UploadFile], files), db
    )
    all_attachments = existing_attachments + uploaded_attachments
    logger.info(
        f"Total attachments: {len(all_attachments)} "
        f"(existing={len(existing_attachments)}, uploaded={len(uploaded_attachments)})"
    )

    if not message.strip() and not all_attachments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "empty_chat_input",
                "message": "Provide a message or at least one attachment",
            },
        )

    generator = await stream_chat_response(
        message,
        thread,
        current_user,
        db,
        attachments=all_attachments,
        interaction_mode=mode,
    )

    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/{thread_id}/process-image")
async def process_image(
    thread_id: str,
    image_base64: str,
    operation: str,  # "change_color", "brightness", "contrast", "resize", "analyze"
    params: dict[str, Any] | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Process an image with specified operation.
    
    Operations:
    - change_color: Change object color (params: object_description, target_color (RGB tuple), tolerance)
    - brightness: Adjust brightness (params: factor)
    - contrast: Adjust contrast (params: factor)
    - resize: Resize image (params: max_width, max_height)
    - analyze: Get image analysis (params: none)
    """
    await get_thread(thread_id, current_user, db)  # ownership check
    params = params or {}
    
    try:
        if operation == "change_color":
            object_desc = params.get("object_description", "")
            target_color = params.get("target_color", (255, 255, 255))
            tolerance = params.get("tolerance", 30)
            modified_base64 = await ImageProcessingService.change_object_color(
                image_base64, object_desc, tuple(target_color), tolerance
            )
            return {
                "success": True,
                "operation": operation,
                "image": modified_base64,
                "message": f"Successfully changed color of {object_desc}",
            }
        
        elif operation == "brightness":
            factor = params.get("factor", 1.0)
            modified_base64 = await ImageProcessingService.adjust_brightness(
                image_base64, factor
            )
            return {
                "success": True,
                "operation": operation,
                "image": modified_base64,
                "message": f"Adjusted brightness by factor {factor}",
            }
        
        elif operation == "contrast":
            factor = params.get("factor", 1.0)
            modified_base64 = await ImageProcessingService.adjust_contrast(
                image_base64, factor
            )
            return {
                "success": True,
                "operation": operation,
                "image": modified_base64,
                "message": f"Adjusted contrast by factor {factor}",
            }
        
        elif operation == "resize":
            max_width = params.get("max_width", 800)
            max_height = params.get("max_height", 600)
            modified_base64 = await ImageProcessingService.resize_image(
                image_base64, max_width, max_height
            )
            return {
                "success": True,
                "operation": operation,
                "image": modified_base64,
                "message": f"Resized image to fit {max_width}x{max_height}",
            }
        
        elif operation == "analyze":
            analysis = await ImageProcessingService.analyze_image_content(image_base64)
            return {
                "success": True,
                "operation": operation,
                "analysis": analysis,
                "message": "Image analyzed successfully",
            }
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "unknown_operation",
                    "message": f"Unknown operation: {operation}",
                },
            )
    
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "image_processing_failed",
                "message": str(e),
            },
        )


# ---------------------------------------------------------------------------
# PDF / RAG endpoints
# ---------------------------------------------------------------------------

@router.post("/{thread_id}/documents", response_model=DocumentUploadResponse)
async def upload_document(
    thread_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a PDF and ingest it into ChromaDB for RAG.

    - Validates MIME type (must be application/pdf).
    - Deduplicates by file hash — same content is never re-embedded.
    - Returns the document record and whether it was already processed.
    """
    thread = await get_thread(thread_id, current_user, db)

    # Validate MIME type server-side (do not trust file extension)
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        # Allow octet-stream fallback but still check extension
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={"error": "invalid_mime", "message": "Only PDF files are accepted."},
            )

    file_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "file_too_large",
                "message": f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit.",
            },
        )

    try:
        doc, already_processed = await ingest_document(
            db,
            file_bytes=file_bytes,
            filename=file.filename or "document.pdf",
            user_id=current_user.id,
            thread_id=thread.id,
            user_email=current_user.email,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "ingestion_failed", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.error("Unexpected document ingestion failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "ingestion_failed",
                "message": "Could not process this PDF right now. Please try again with a different file or re-upload.",
            },
        ) from exc

    message = (
        "Document already processed — using existing embeddings."
        if already_processed
        else f"Document '{doc.filename}' ingested successfully ({doc.chunk_count} chunks)."
    )
    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(doc),
        already_processed=already_processed,
        message=message,
    )


@router.get("/{thread_id}/documents", response_model=list[DocumentResponse])
async def get_documents(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """List all documents uploaded to this thread."""
    await get_thread(thread_id, current_user, db)
    docs = await list_documents_for_thread(db, uuid.UUID(thread_id), current_user.id)
    return [DocumentResponse.model_validate(d) for d in docs]
