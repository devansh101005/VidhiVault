import os
import uuid
import hashlib

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import Document
from app.api.schemas.documents import DocumentUploadResponse
from app.workers.tasks import process_document


router = APIRouter(prefix="/documents", tags=["documents"])


# Ensure uploads directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # ---------------------------
    # Validate file type
    # ---------------------------
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # ---------------------------
    # Read file content
    # ---------------------------
    content = await file.read()

    # ---------------------------
    # Compute SHA256 hash
    # ---------------------------
    file_hash = hashlib.sha256(content).hexdigest()

    # ---------------------------
    # Check for duplicate
    # ---------------------------
    result = await db.execute(
        select(Document).where(Document.file_hash == file_hash)
    )
    existing_doc = result.scalar_one_or_none()

    if existing_doc:
        return DocumentUploadResponse.model_validate(existing_doc)

    
    # Save file to disk
    
    file_id = uuid.uuid4()
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(content)


    # Create DB record
    doc = Document(
        title=file.filename,
        file_path=file_path,
        file_hash=file_hash,
        # processing_status defaults to "pending"
    )

    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    process_document.delay(str(doc.id))

    
    # Return response
    return DocumentUploadResponse.model_validate(doc)