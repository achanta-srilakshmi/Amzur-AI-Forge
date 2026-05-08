"""Attachment storage and extraction service."""
import base64
import csv
import logging
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from openai import OpenAIError
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import openai_client
from app.core.config import settings
from app.models.attachment import Attachment, AttachmentKind
from app.models.message import Message
from app.models.thread import Thread
from app.models.user import User

logger = logging.getLogger(__name__)

_MAX_EXTRACT_CHARS = 6000
_CSV_PREVIEW_ROWS = 20
_PDF_PREVIEW_PAGES = 10
_BASE64_PREVIEW_SOURCE_BYTES = 3072
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
_TEXT_EXTENSIONS = {".txt", ".md", ".rtf"}
_TABLE_EXTENSIONS = {".csv", ".xls", ".xlsx"}
_PDF_EXTENSIONS = {".pdf"}
_FORMULA_EXTENSIONS = {".tex", ".latex", ".katex", ".mathml", ".mml"}
_CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".cpp",
    ".c",
    ".h",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".sql",
    ".html",
    ".css",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".sh",
    ".ps1",
    ".md",
}


def _sanitize_filename(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")


def _normalize_mime_type(filename: str, mime_type: str) -> str:
    normalized = mime_type.strip().lower()
    if normalized and normalized != "application/octet-stream":
        return normalized

    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed.lower()

    return "application/octet-stream"


def _detect_kind(filename: str, mime_type: str) -> AttachmentKind:
    ext = Path(filename).suffix.lower()

    if mime_type.startswith("image/") or ext in _IMAGE_EXTENSIONS:
        return AttachmentKind.image
    if mime_type.startswith("video/") or ext in _VIDEO_EXTENSIONS:
        return AttachmentKind.video
    if mime_type == "application/pdf" or ext in _PDF_EXTENSIONS:
        return AttachmentKind.pdf
    if mime_type == "text/csv" or ext in _TABLE_EXTENSIONS:
        return AttachmentKind.table
    if ext in _FORMULA_EXTENSIONS:
        return AttachmentKind.formula
    if ext in _CODE_EXTENSIONS:
        return AttachmentKind.code
    if mime_type.startswith("text/") or ext in _TEXT_EXTENSIONS:
        return AttachmentKind.text

    return AttachmentKind.other


def _is_allowed_upload(filename: str, mime_type: str) -> bool:
    ext = Path(filename).suffix.lower()
    if mime_type in settings.ACCEPTED_MIME_TYPES:
        return True
    if ext in _IMAGE_EXTENSIONS | _VIDEO_EXTENSIONS | _TABLE_EXTENSIONS | _TEXT_EXTENSIONS | _PDF_EXTENSIONS | _FORMULA_EXTENSIONS:
        return True
    if ext in _CODE_EXTENSIONS:
        return True
    return False


def _encode_base64_preview(path: Path) -> str:
    raw_bytes = path.read_bytes()
    truncated = len(raw_bytes) > _BASE64_PREVIEW_SOURCE_BYTES
    preview_bytes = raw_bytes[:_BASE64_PREVIEW_SOURCE_BYTES]
    encoded = base64.b64encode(preview_bytes).decode("utf-8")
    if truncated:
        return f"{encoded}...[truncated]"
    return encoded


async def save_attachments(
    thread: Thread,
    user: User,
    files: list[UploadFile],
    db: AsyncSession,
) -> list[Attachment]:
    upload_root = Path(settings.UPLOAD_DIR)
    saved: list[Attachment] = []

    for file in files:
        original_filename = _sanitize_filename(file.filename or "upload.bin")
        mime_type = _normalize_mime_type(
            original_filename, file.content_type or ""
        )

        if not _is_allowed_upload(original_filename, mime_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_file_type",
                    "message": f"Unsupported attachment type for {original_filename}",
                },
            )

        data = await file.read()
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "file_too_large",
                    "message": (
                        f"{original_filename} exceeds max upload size "
                        f"of {settings.MAX_UPLOAD_MB} MB"
                    ),
                },
            )

        kind = _detect_kind(original_filename, mime_type)
        suffix = Path(original_filename).suffix
        stored_filename = f"{uuid.uuid4()}{suffix}"
        relative_dir = Path(str(user.id)) / str(thread.id)
        relative_path = relative_dir / stored_filename

        full_dir = upload_root / relative_dir
        full_dir.mkdir(parents=True, exist_ok=True)
        full_path = upload_root / relative_path
        full_path.write_bytes(data)

        attachment = Attachment(
            id=uuid.uuid4(),
            thread_id=thread.id,
            user_id=user.id,
            message_id=None,
            original_filename=original_filename,
            stored_filename=stored_filename,
            storage_path=relative_path.as_posix(),
            mime_type=mime_type,
            size_bytes=len(data),
            kind=kind,
            extracted_text=None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(attachment)
        saved.append(attachment)

    await db.commit()
    for attachment in saved:
        await db.refresh(attachment)

    return saved


async def load_attachments_for_thread(
    attachment_ids: list[uuid.UUID],
    thread: Thread,
    user: User,
    db: AsyncSession,
) -> list[Attachment]:
    if not attachment_ids:
        return []

    result = await db.execute(
        select(Attachment).where(
            Attachment.id.in_(attachment_ids),
            Attachment.thread_id == thread.id,
            Attachment.user_id == user.id,
        )
    )
    attachments = list(result.scalars().all())

    if len(attachments) != len(set(attachment_ids)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "attachment_not_found",
                "message": "One or more attachments were not found for this thread",
            },
        )

    return attachments


async def bind_attachments_to_message(
    attachments: list[Attachment],
    message: Message,
    db: AsyncSession,
) -> None:
    for attachment in attachments:
        attachment.message_id = message.id
    await db.commit()


def _extract_csv(path: Path) -> str:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader):
            if idx >= _CSV_PREVIEW_ROWS:
                break
            rows.append({k: (v or "") for k, v in row.items()})

    return (
        "CSV preview (first rows as JSON-like records):\n"
        f"{rows}" if rows else "CSV file is empty or has no parseable rows."
    )


def _extract_table(path: Path) -> str:
    if path.suffix.lower() == ".csv":
        return _extract_csv(path)

    dataframe = pd.read_excel(path).fillna("")
    preview = dataframe.head(_CSV_PREVIEW_ROWS).to_dict(orient="records")
    columns = [str(column) for column in dataframe.columns.tolist()]
    return (
        "Tabular preview:\n"
        f"columns: {columns}\n"
        f"rows: {preview}"
    )


def _extract_text(path: Path) -> str:
    content = path.read_text(encoding="utf-8", errors="ignore")
    return content[:_MAX_EXTRACT_CHARS]


def _extract_code(path: Path) -> str:
    content = path.read_text(encoding="utf-8", errors="ignore")
    ext = path.suffix.lower().lstrip(".") or "text"
    return f"```{ext}\n{content[:_MAX_EXTRACT_CHARS]}\n```"


def _extract_video(path: Path, attachment: Attachment) -> str:
    return (
        "Video attached. Preserved for downstream review with file metadata and base64 preview. "
        f"Filename: {attachment.original_filename}, size_bytes: {path.stat().st_size}, mime_type: {attachment.mime_type}."
    )


def _extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    page_text: list[str] = []
    for page in reader.pages[:_PDF_PREVIEW_PAGES]:
        extracted = (page.extract_text() or "").strip()
        if extracted:
            page_text.append(extracted)

    if not page_text:
        return "PDF attached. No extractable text was found in the first pages."

    return "\n\n".join(page_text)[:_MAX_EXTRACT_CHARS]


def _extract_formula(path: Path) -> str:
    content = path.read_text(encoding="utf-8", errors="ignore")[:_MAX_EXTRACT_CHARS]
    return f"Formula document:\n```latex\n{content}\n```"


def _extract_image(path: Path, mime_type: str, user_email: str) -> str:
    image_bytes = path.read_bytes()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    try:
        logger.info(
            f"Calling LLM vision API for image extraction: model={settings.LLM_MODEL}, "
            f"proxy={settings.LITELLM_PROXY_URL}"
        )
        response = openai_client.chat.completions.create(
            model=settings.LLM_MODEL,
            user=user_email,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert image analyst. Provide detailed, accurate analysis focusing on colors and object counts.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """CRITICAL: Analyze this image with extreme precision.

**STEP 1 - OBJECT IDENTIFICATION (Most Important)**
What is the primary object/subject in this image? Be specific:
- Is it clothing items? (gloves, shirts, hats, shoes, jackets, etc.)
- Is it sports equipment? (balls, bats, helmets, gloves, pads, etc.)
- Is it tools? (wrenches, screwdrivers, hammers, saws, etc.)
- Is it food? (fruits, vegetables, baked goods, etc.)
- Is it other? (describe)
State the exact object type clearly. Examples: "These are baseball gloves", "These are oranges", "These are basketballs"

**STEP 2 - COUNT**
Count the total number of objects present. Be precise: [NUMBER] total

**STEP 3 - COMPREHENSIVE COLOR ANALYSIS**
List EVERY unique color and shade present. For each color/shade, estimate:
- Name: (e.g., "caramel brown", "burnt orange", "charcoal black")
- Count of objects in that color
- % coverage of image

**STEP 4 - MATERIAL & TEXTURE**
Materials visible: (leather, rubber, metal, plastic, fabric, wood, etc.)
Textures: (smooth, rough, creased, worn, weathered, faded, etc.)
Wear patterns: (scuff marks, tears, fading, aging, damage, etc.)

**STEP 5 - SPATIAL ARRANGEMENT**
Describe positioning, layout, rows/columns if applicable, depth levels.

**STEP 6 - DISTINCTIVE FEATURES**
Any logos, text, brand names, patterns, or unique markings?

Output this analysis in clear sections. ACCURACY IS CRITICAL.""",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            extra_body={
                "metadata": {
                    "application": settings.APP_NAME,
                    "environment": settings.ENVIRONMENT,
                }
            },
        )
        message_content = response.choices[0].message.content
        if isinstance(message_content, str):
            logger.info("Image extraction succeeded")
            result = message_content[:_MAX_EXTRACT_CHARS]
            if not result or result.strip() == "":
                logger.warning("Image extraction returned empty content")
                return "[Image attached but vision API returned empty response]"
            return result
        return str(message_content)[:_MAX_EXTRACT_CHARS]
    except OpenAIError as exc:
        error_msg = f"OpenAI/LiteLLM error during image extraction: {type(exc).__name__}: {exc}"
        logger.error(error_msg, exc_info=True)
        return f"[Image attached but extraction failed: {str(exc)[:200]}]"
    except Exception as exc:
        error_msg = f"Unexpected error during image extraction: {type(exc).__name__}: {exc}"
        logger.error(error_msg, exc_info=True)
        return f"[Image attached but extraction failed: {str(exc)[:200]}]"


async def extract_attachment_text(
    attachment: Attachment,
    user_email: str,
    db: AsyncSession,
) -> str:
    if attachment.extracted_text:
        cached = attachment.extracted_text.strip()
        retryable_failure = (
            cached.startswith("[Image attached but extraction failed")
            or cached.startswith("[Image attached but vision API returned empty response")
            or cached.startswith("Attachment file not found on disk")
            or cached.startswith("[PDF extraction failed")
            or "can't view" in cached.lower()
            or "cannot view" in cached.lower()
            or "no parser is configured" in cached
        )
        if not retryable_failure:
            logger.debug(f"Using cached extraction for attachment {attachment.id}")
            return attachment.extracted_text
        logger.info(
            f"Retrying extraction for attachment {attachment.id} due to cached failure"
        )

    file_path = Path(settings.UPLOAD_DIR) / attachment.storage_path
    logger.info(
        f"Extracting attachment: filename={attachment.original_filename}, "
        f"kind={attachment.kind.value}, mime_type={attachment.mime_type}"
    )
    
    _is_pdf = (
        attachment.mime_type == "application/pdf"
        or Path(attachment.original_filename).suffix.lower() == ".pdf"
    )

    if not file_path.exists():
        extracted = f"Attachment file not found on disk: {attachment.original_filename}"
        logger.warning(f"Attachment file not found: {file_path}")
    elif _is_pdf:
        # Handle PDFs regardless of stored kind (old records may have kind=other)
        extracted = _extract_pdf(file_path)
        logger.debug(f"PDF extraction completed for {attachment.original_filename}")
    elif attachment.kind == AttachmentKind.image:
        extracted = _extract_image(file_path, attachment.mime_type, user_email)
    elif attachment.kind == AttachmentKind.table:
        extracted = _extract_table(file_path)
        logger.debug(f"Table extraction completed for {attachment.original_filename}")
    elif attachment.kind == AttachmentKind.pdf:
        extracted = _extract_pdf(file_path)
        logger.debug(f"PDF extraction completed for {attachment.original_filename}")
    elif attachment.kind == AttachmentKind.formula:
        extracted = _extract_formula(file_path)
        logger.debug(f"Formula extraction completed for {attachment.original_filename}")
    elif attachment.kind == AttachmentKind.code:
        extracted = _extract_code(file_path)
        logger.debug(f"Code extraction completed for {attachment.original_filename}")
    elif attachment.kind == AttachmentKind.text:
        extracted = _extract_text(file_path)
        logger.debug(f"Text extraction completed for {attachment.original_filename}")
    elif attachment.kind == AttachmentKind.video:
        extracted = _extract_video(file_path, attachment)
        logger.debug(f"Video extraction completed for {attachment.original_filename}")
    else:
        extracted = (
            "Attachment type accepted but no parser is configured. "
            f"Filename: {attachment.original_filename}, MIME: {attachment.mime_type}."
        )
        logger.warning(f"No parser configured for attachment kind: {attachment.kind}")

    attachment.extracted_text = extracted[:_MAX_EXTRACT_CHARS]
    await db.commit()
    return attachment.extracted_text


async def list_attachments_for_thread(
    thread: Thread,
    user: User,
    db: AsyncSession,
) -> list[Attachment]:
    result = await db.execute(
        select(Attachment)
        .where(
            Attachment.thread_id == thread.id,
            Attachment.user_id == user.id,
        )
        .order_by(Attachment.created_at.asc())
    )
    return list(result.scalars().all())


async def build_attachment_context(
    attachments: list[Attachment],
    user_email: str,
    db: AsyncSession,
) -> str:
    if not attachments:
        logger.debug("No attachments to build context from")
        return ""

    logger.info(f"Building attachment context for {len(attachments)} attachment(s)")
    blocks: list[str] = []
    for idx, attachment in enumerate(attachments, start=1):
        logger.info(
            f"Processing attachment {idx}/{len(attachments)}: "
            f"{attachment.original_filename} (kind={attachment.kind.value})"
        )
        extracted = await extract_attachment_text(attachment, user_email, db)
        file_path = Path(settings.UPLOAD_DIR) / attachment.storage_path
        base64_preview = (
            _encode_base64_preview(file_path) if file_path.exists() else "[missing-file]"
        )
        
        # Log first 100 chars of extracted text for debugging
        extract_preview = extracted.replace("\n", " ")[:100]
        logger.debug(f"Extracted content preview: {extract_preview}")
        
        blocks.append(
            "\n".join(
                [
                    f"Attachment {idx}",
                    f"filename: {attachment.original_filename}",
                    f"mime_type: {attachment.mime_type}",
                    f"kind: {attachment.kind.value}",
                    f"storage_path: {attachment.storage_path}",
                    f"base64_preview: {base64_preview}",
                    "content:",
                    extracted,
                ]
            )
        )

    result = "\n\n".join(blocks)
    logger.info(f"Attachment context built. Total length: {len(result)} chars")
    return result
