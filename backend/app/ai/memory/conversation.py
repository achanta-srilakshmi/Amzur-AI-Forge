"""Conversation memory — rolling window of the last k turn-pairs per thread."""
import uuid

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageRole

# Number of human+AI turn pairs to retain in the context window.
# Increase to allow more history; decrease to reduce token usage.
MEMORY_WINDOW_K: int = 5


class ThreadMemory:
    """Fetches the last k turn-pairs for a thread and returns them as
    a list[BaseMessage] ready for injection into a MessagesPlaceholder."""

    def __init__(self, k: int = MEMORY_WINDOW_K) -> None:
        self.k = k

    async def load(
        self, thread_id: uuid.UUID, db: AsyncSession
    ) -> list[BaseMessage]:
        """Return at most k*2 messages (k pairs) in chronological order."""
        result = await db.execute(
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at.desc())
            .limit(self.k * 2)
        )
        rows = list(reversed(result.scalars().all()))

        messages: list[BaseMessage] = []
        for row in rows:
            if row.role == MessageRole.user:
                messages.append(HumanMessage(content=row.content))
            elif row.role == MessageRole.assistant:
                messages.append(AIMessage(content=row.content))

        return messages


# Module-level singleton — import this in chat_service.py
thread_memory = ThreadMemory(k=MEMORY_WINDOW_K)


async def load_history(thread_id: str, db: AsyncSession) -> list[BaseMessage]:
    """Backward-compatibility shim. Delegates to thread_memory.load().
    Effective history limit is now MEMORY_WINDOW_K*2 messages (default 10),
    down from the previous hard-coded limit of 20."""
    return await thread_memory.load(uuid.UUID(thread_id), db)
