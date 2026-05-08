import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    thread_id: uuid.UUID
    filename: str
    file_path: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    already_processed: bool
    message: str
