from datetime import datetime

from pydantic import BaseModel, field_validator


class AttachmentResponse(BaseModel):
    id: str
    thread_id: str
    user_id: str
    message_id: str | None
    original_filename: str
    mime_type: str
    size_bytes: int
    kind: str
    storage_path: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "thread_id", "user_id", "message_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v)
