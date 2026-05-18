"""Schemas for Ask your Data API."""

from pydantic import BaseModel


class AskDataResponse(BaseModel):
    question: str
    pandas_operation: str
    answer: str
