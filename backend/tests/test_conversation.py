import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.memory.conversation import ThreadMemory, thread_memory, load_history
from app.models.message import Message, MessageRole

@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_thread_memory_load_pairs_only(mock_db):
    # Prepare 3 user/assistant pairs (6 messages)
    messages = [
        Message(id=uuid.uuid4(), thread_id=uuid.uuid4(), user_id=uuid.uuid4(), role=MessageRole.user, content="hi", created_at=None),
        Message(id=uuid.uuid4(), thread_id=uuid.uuid4(), user_id=uuid.uuid4(), role=MessageRole.assistant, content="hello", created_at=None),
        Message(id=uuid.uuid4(), thread_id=uuid.uuid4(), user_id=uuid.uuid4(), role=MessageRole.user, content="how are you?", created_at=None),
        Message(id=uuid.uuid4(), thread_id=uuid.uuid4(), user_id=uuid.uuid4(), role=MessageRole.assistant, content="I'm good", created_at=None),
        Message(id=uuid.uuid4(), thread_id=uuid.uuid4(), user_id=uuid.uuid4(), role=MessageRole.user, content="bye", created_at=None),
        Message(id=uuid.uuid4(), thread_id=uuid.uuid4(), user_id=uuid.uuid4(), role=MessageRole.assistant, content="bye!", created_at=None),
    ]
    # Simulate DB returning messages in DESC order
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = list(reversed(messages))
    mock_db.execute.return_value = mock_result
    out = await thread_memory.load(messages[0].thread_id, mock_db)
    assert len(out) == 6
    assert out[0].content == "hi"
    assert out[1].content == "hello"
    assert out[-2].content == "bye"
    assert out[-1].content == "bye!"

@pytest.mark.asyncio
async def test_thread_memory_load_skips_unpaired(mock_db):
    # Only user messages, no assistant replies
    messages = [
        Message(id=uuid.uuid4(), thread_id=uuid.uuid4(), user_id=uuid.uuid4(), role=MessageRole.user, content="hi", created_at=None),
        Message(id=uuid.uuid4(), thread_id=uuid.uuid4(), user_id=uuid.uuid4(), role=MessageRole.user, content="how are you?", created_at=None),
    ]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = list(reversed(messages))
    mock_db.execute.return_value = mock_result
    out = await thread_memory.load(messages[0].thread_id, mock_db)
    assert out == []

@pytest.mark.asyncio
async def test_load_history_shim_delegates(mock_db):
    # Should call thread_memory.load with UUID
    called = {}
    async def fake_load(thread_id, db):
        called['thread_id'] = thread_id
        called['db'] = db
        return ["ok"]
    orig = thread_memory.load
    thread_memory.load = fake_load
    try:
        result = await load_history(str(uuid.uuid4()), mock_db)
        assert result == ["ok"]
        assert called['db'] is mock_db
    finally:
        thread_memory.load = orig
