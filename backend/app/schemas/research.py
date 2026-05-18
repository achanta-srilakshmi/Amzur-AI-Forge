"""Schemas for research digest API."""

from pydantic import BaseModel, Field


class ResearchDigestRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Research topic to investigate")
