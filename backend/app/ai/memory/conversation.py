"""Conversation memory — fetches thread history from DB as LangChain messages."""
import uuid

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageRole


async def load_history(thread_id: str, db: AsyncSession) -> list[BaseMessage]:
    """Return the last 20 messages of a thread as LangChain message objects."""
    result = await db.execute(
        select(Message)
        .where(Message.thread_id == uuid.UUID(thread_id))
        .order_by(Message.created_at.asc())
        .limit(20)
    )
    messages = result.scalars().all()
    history: list[BaseMessage] = []
    for msg in messages:
        if msg.role == MessageRole.user:
            history.append(HumanMessage(content=msg.content))
        else:
            history.append(AIMessage(content=msg.content))
    return history
