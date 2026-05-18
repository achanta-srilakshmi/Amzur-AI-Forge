from pydantic import BaseModel, Field


class NLQueryRequest(BaseModel):
    question: str = Field(min_length=1)


class NLQueryResponse(BaseModel):
    question: str
    sql: str
    answer: str