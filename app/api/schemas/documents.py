from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict
from app.workers.tasks import process_document

#response after doc upload
class DocumentUploadResponse(BaseModel):
    id: UUID
    title: str
    processing_status: str
    created_at: datetime

    # allow reading from SQLAlchemy ORM objects
    model_config = ConfigDict(from_attributes=True)


 #response for list
class DocumentOut(BaseModel):
    id: UUID
    title: str
    processing_status: str
    created_at: datetime

    total_pages: Optional[int] = None
    total_chunks: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)