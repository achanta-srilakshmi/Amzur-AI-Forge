import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generated_image import GeneratedImage
from app.models.message import MessageRole
from app.models.thread import Thread
from app.models.user import User
from app.services import chat_service


async def _chunk_stream(chunks: list[str]):
    for chunk in chunks:
        yield chunk

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.fixture
def mock_thread():
    return Thread(id=uuid.uuid4(), title="New Chat", updated_at=None)

@pytest.fixture
def mock_user():
    return User(id=uuid.uuid4(), email="test@amzur.com")

@pytest.mark.asyncio
async def test_stream_chat_response_saves_and_streams(mock_db, mock_thread, mock_user):
    mock_chain = MagicMock()
    mock_chain.astream = MagicMock(return_value=_chunk_stream(["Hello", " world"]))

    with patch("app.services.chat_service._save_message", new=AsyncMock()) as save_msg, \
         patch("app.services.chat_service.chat_chain", new=mock_chain):
        # Patch thread_memory.load to return empty history
        with patch("app.services.chat_service.thread_memory.load", new=AsyncMock(return_value=[])):
            gen = await chat_service.stream_chat_response(
                "hi", mock_thread, mock_user, mock_db
            )
            out = []
            async for chunk in gen:
                out.append(chunk)
            assert "Hello" in out[0]
        # Ensure _save_message called for user and assistant
        assert save_msg.await_count >= 2

@pytest.mark.asyncio
async def test_stream_chat_response_handles_llm_error(mock_db, mock_thread, mock_user):
    mock_chain = MagicMock()
    mock_chain.astream = MagicMock(side_effect=Exception("fail"))

    with patch("app.services.chat_service._save_message", new=AsyncMock()), \
         patch("app.services.chat_service.chat_chain", new=mock_chain):
        with patch("app.services.chat_service.thread_memory.load", new=AsyncMock(return_value=[])):
            gen = await chat_service.stream_chat_response(
                "hi", mock_thread, mock_user, mock_db
            )
            out = []
            async for chunk in gen:
                out.append(chunk)
            assert any(
                "Error communicating" in c or "Unexpected error" in c for c in out
            )


@pytest.mark.asyncio
async def test_stream_chat_response_returns_generated_image_when_intent_true(
    mock_db, mock_thread, mock_user
):
    generated_id = uuid.uuid4()
    generated = GeneratedImage(
        id=generated_id,
        thread_id=mock_thread.id,
        user_id=mock_user.id,
        prompt="draw a sunset",
        image_base64="ZmFrZQ==",
        image_url=None,
        mime_type="image/png",
        provider_model="gemini/imagen-4.0-fast-generate-001",
        created_at=datetime.now(timezone.utc),
    )

    with patch("app.services.chat_service._save_message", new=AsyncMock()) as save_msg, \
         patch("app.services.chat_service.detect_image_generation_intent", new=AsyncMock(return_value=True)), \
         patch("app.services.chat_service.generate_image_for_prompt", new=AsyncMock(return_value=generated)), \
         patch("app.services.chat_service._message_count", new=AsyncMock(return_value=0)), \
         patch("app.services.chat_service._generate_title", new=AsyncMock(return_value="Sunset art")), \
         patch("app.services.chat_service.build_attachment_context", new=AsyncMock(return_value="")):
        gen = await chat_service.stream_chat_response(
            "draw a sunset", mock_thread, mock_user, mock_db
        )
        out = []
        async for chunk in gen:
            out.append(chunk)

    assert len(out) == 1
    assert "/generated-images/" in out[0]
    assert save_msg.await_count >= 2


@pytest.mark.asyncio
async def test_stream_chat_response_falls_back_to_text_when_image_fails(
    mock_db, mock_thread, mock_user
):
    mock_chain = MagicMock()
    mock_chain.astream = MagicMock(return_value=_chunk_stream(["fallback text"]))

    with patch("app.services.chat_service._save_message", new=AsyncMock()) as save_msg, \
         patch("app.services.chat_service.chat_chain", new=mock_chain), \
         patch("app.services.chat_service.detect_image_generation_intent", new=AsyncMock(return_value=True)), \
         patch("app.services.chat_service.generate_image_for_prompt", new=AsyncMock(side_effect=Exception("boom"))), \
         patch("app.services.chat_service._message_count", new=AsyncMock(return_value=0)), \
         patch("app.services.chat_service._generate_title", new=AsyncMock(return_value="Fallback")), \
         patch("app.services.chat_service.build_attachment_context", new=AsyncMock(return_value="")), \
         patch("app.services.chat_service.thread_memory.load", new=AsyncMock(return_value=[])):
        gen = await chat_service.stream_chat_response(
            "generate an image", mock_thread, mock_user, mock_db
        )
        out = []
        async for chunk in gen:
            out.append(chunk)

    assert any("fallback text" in chunk for chunk in out)
    assert save_msg.await_count >= 2
