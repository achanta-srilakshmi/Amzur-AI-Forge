"""Ask your Data API routes."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.ask_data import AskDataResponse
from app.services.ask_data_service import run_ask_data_query
from app.services.auth_service import get_current_user

router = APIRouter()


@router.post("/query", response_model=AskDataResponse)
async def query_ask_data(
    question: str = Form(...),
    input_method: str = Form(...),
    google_sheet_url: str | None = Form(None),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AskDataResponse:
    result = await run_ask_data_query(
        question=question,
        input_method=input_method,
        current_user=current_user,
        file=file,
        google_sheet_url=google_sheet_url,
        db=db,
    )
    return AskDataResponse(**result)
