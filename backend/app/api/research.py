"""Research digest streaming API routes."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.models.user import User
from app.schemas.research import ResearchDigestRequest
from app.services.auth_service import get_current_user
from app.services.research_service import run_research_agent

router = APIRouter()


@router.post("/digest")
async def stream_research_digest(
    payload: ResearchDigestRequest,
    mode: Literal["standard", "mcp"] = Query(default="standard"),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    if mode == "mcp":
        from app.services.research_mcp_service import run_mcp_research_agent

        generator = run_mcp_research_agent(payload.topic, current_user)
    else:
        generator = run_research_agent(payload.topic, current_user)
    return StreamingResponse(generator, media_type="text/event-stream")
