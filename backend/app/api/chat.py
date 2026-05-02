"""Chat routes — message history and streaming LLM response."""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.message import Message
from app.models.user import User
from app.schemas.message import ChatRequest, MessageResponse
from app.services.auth_service import get_current_user
from app.services.chat_service import list_messages, stream_chat_response
from app.services.thread_service import get_thread

router = APIRouter()


@router.get("/{thread_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Message]:
    await get_thread(thread_id, current_user, db)  # ownership check
    return await list_messages(thread_id, db)


@router.post("/{thread_id}/chat")
async def chat(
    thread_id: str,
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    thread = await get_thread(thread_id, current_user, db)
    generator = await stream_chat_response(data.message, thread, current_user, db)

    return StreamingResponse(generator, media_type="text/event-stream")
