from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pypdf import PdfWriter

from app.models.attachment import Attachment, AttachmentKind
from app.services import attachment_service


@pytest.mark.parametrize(
    ("filename", "mime_type", "expected"),
    [
        ("diagram.png", "image/png", AttachmentKind.image),
        ("demo.mov", "video/quicktime", AttachmentKind.video),
        ("sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", AttachmentKind.table),
        ("notes.pdf", "application/pdf", AttachmentKind.pdf),
        ("equation.tex", "text/x-tex", AttachmentKind.formula),
        ("main.ts", "text/plain", AttachmentKind.code),
        ("notes.txt", "text/plain", AttachmentKind.text),
    ],
)
def test_detect_kind_supports_multimodal_inputs(filename, mime_type, expected):
    assert attachment_service._detect_kind(filename, mime_type) == expected


@pytest.mark.asyncio
async def test_build_attachment_context_includes_base64_preview(tmp_path, monkeypatch):
    uploads_dir = tmp_path / "uploads"
    file_dir = uploads_dir / "user-1" / "thread-1"
    file_dir.mkdir(parents=True)
    file_path = file_dir / "notes.txt"
    file_path.write_text("Important context for the model.", encoding="utf-8")

    monkeypatch.setattr(attachment_service.settings, "UPLOAD_DIR", str(uploads_dir))

    attachment = Attachment(
        original_filename="notes.txt",
        storage_path=Path("user-1/thread-1/notes.txt").as_posix(),
        mime_type="text/plain",
        kind=AttachmentKind.text,
        extracted_text=None,
    )
    db = AsyncMock()

    context = await attachment_service.build_attachment_context(
        [attachment], "user@amzur.com", db
    )

    assert "base64_preview:" in context
    assert "Important context for the model." in context
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_extract_attachment_text_reads_pdf(tmp_path, monkeypatch):
    uploads_dir = tmp_path / "uploads"
    file_dir = uploads_dir / "user-1" / "thread-1"
    file_dir.mkdir(parents=True)
    pdf_path = file_dir / "blank.pdf"

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pdf_path.open("wb") as handle:
        writer.write(handle)

    monkeypatch.setattr(attachment_service.settings, "UPLOAD_DIR", str(uploads_dir))

    attachment = Attachment(
        original_filename="blank.pdf",
        storage_path=Path("user-1/thread-1/blank.pdf").as_posix(),
        mime_type="application/pdf",
        kind=AttachmentKind.pdf,
        extracted_text=None,
    )
    db = AsyncMock()

    extracted = await attachment_service.extract_attachment_text(
        attachment, "user@amzur.com", db
    )

    assert "PDF attached." in extracted
    db.commit.assert_awaited()