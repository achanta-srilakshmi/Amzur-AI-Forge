from unittest.mock import AsyncMock, patch

import pytest

from app.services.intent_service import detect_image_generation_intent


@pytest.mark.asyncio
async def test_detect_image_generation_intent_keyword_hit() -> None:
    result = await detect_image_generation_intent(
        "Please generate an image of a futuristic city", "user@amzur.com"
    )
    assert result is True


@pytest.mark.asyncio
async def test_detect_image_generation_intent_llm_fallback_yes() -> None:
    fake_result = type("LLMResult", (), {"content": "YES"})()
    fake_llm = type("FakeLLM", (), {"ainvoke": AsyncMock(return_value=fake_result)})()
    with patch("app.services.intent_service.llm", new=fake_llm):
        result = await detect_image_generation_intent(
            "Make something creative for me", "user@amzur.com"
        )
    assert result is True


@pytest.mark.asyncio
async def test_detect_image_generation_intent_llm_fallback_error_defaults_false() -> None:
    fake_llm = type("FakeLLM", (), {"ainvoke": AsyncMock(side_effect=Exception("fail"))})()
    with patch("app.services.intent_service.llm", new=fake_llm):
        result = await detect_image_generation_intent(
            "Can you help with this?", "user@amzur.com"
        )
    assert result is False
