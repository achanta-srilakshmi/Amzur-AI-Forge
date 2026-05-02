from datetime import datetime

from pydantic import BaseModel, field_validator


class ChatRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "thread_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str:
        return str(v)
