from fastapi import APIRouter, Depends

from app.models.user import User
from app.schemas.n8n import TriggerPrReviewRequest, TriggerPrReviewResponse
from app.services.auth_service import get_current_user
from app.services.n8n_service import trigger_pr_review

router = APIRouter()


@router.post("/trigger-pr-review", response_model=TriggerPrReviewResponse)
async def trigger_n8n_pr_review(
    payload: TriggerPrReviewRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    return await trigger_pr_review(payload.github_pr_url, current_user)
