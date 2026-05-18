"""NL-to-SQL API routes."""

from fastapi import APIRouter, Depends

from app.models.user import User
from app.schemas.nl_to_sql import NLQueryRequest, NLQueryResponse
from app.services.auth_service import get_current_user
from app.services.nl_to_sql_service import run_nl_query

router = APIRouter()


@router.post("/query", response_model=NLQueryResponse)
async def query(
    data: NLQueryRequest,
    current_user: User = Depends(get_current_user),
) -> NLQueryResponse:
    result = await run_nl_query(data.question, current_user)
    return NLQueryResponse(**result)