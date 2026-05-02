"""
Chat service — saves messages and streams LLM responses.
"""
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from openai import OpenAIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chains.chat_chain import chat_chain
from app.ai.llm import llm
from app.ai.memory.conversation import load_history
from app.models.message import Message, MessageRole
from app.models.thread import Thread
from app.models.user import User

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
        title = str(result.content).strip().strip('"').strip("'")
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
) -> AsyncGenerator[str, None]:
    """
    1. Auto-title thread from first user message (if still default).
    2. Persist user message.
    3. Stream LLM reply token-by-token.
    4. Persist full assistant response after streaming completes.
    """
    # Auto-title: generate a meaningful title from the first user message
    msg_count = await _message_count(thread.id, db)
    if msg_count == 0 and thread.title in ("New Chat", "New conversation"):
        thread.title = await _generate_title(user_message, user.email)

    # Persist user message and bump updated_at
    await _save_message(db, thread.id, user.id, MessageRole.user, user_message)
    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Load history excluding the message just saved
    history = await load_history(str(thread.id), db)
    if history and getattr(history[-1], "content", None) == user_message:
        history = history[:-1]

    full_response: list[str] = []

    async def _generate() -> AsyncGenerator[str, None]:
        try:
            async for chunk in chat_chain.astream(
                {"human_input": user_message, "history": history},
                config={"metadata": {"user_email": user.email}},
            ):
                full_response.append(chunk)
                yield chunk
        except OpenAIError as exc:
            yield f"\n\n[Error communicating with the AI: {exc}]"
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
