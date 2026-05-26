from pydantic import BaseModel


class TriggerPrReviewRequest(BaseModel):
    github_pr_url: str


class TriggerPrReviewResponse(BaseModel):
    status: str
    pr_url: str
    message: str
