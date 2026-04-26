from celery import Celery
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from app.config import settings
from app.db.models import Document
from app.core.parser import parse_pdf
from app.core.chunker import chunk_document, ChunkingConfig
from app.core.embedder import Embedder
from app.db.models import Chunk


# Celery app
celery_app = Celery(
    "legal_qa",
    broker=settings.redis_url,
    backend=settings.redis_url
)

# SYNC DB engine for Celery (important)
sync_db_url = settings.database_url.replace("+asyncpg", "")
engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(bind=engine)


@celery_app.task(bind=True)
def process_document(self, document_id: str):
    db = SessionLocal()

    try:
        # 1. Fetch document
        doc = db.execute(
            select(Document).where(Document.id == document_id)
        ).scalar_one()

        doc.processing_status = "processing"
        db.commit()

        # 2. Parse PDF
        parsed = parse_pdf(doc.file_path)

        # 3. Chunk
        chunks = chunk_document(parsed["pages"], ChunkingConfig())

        # attach document_id to each chunk
        for c in chunks:
            c["document_id"] = doc.id

        # 4. Embed
        embedder = Embedder()
        texts = [c["content"] for c in chunks]
        embeddings = embedder.embed_texts(texts)

        # 5. Store chunks
        for chunk, emb in zip(chunks, embeddings):
            db_chunk = Chunk(
                document_id=chunk["document_id"],
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                page_number=chunk["page_number"],
                section_header=chunk["section_header"],
                token_count=chunk["token_count"],
                embedding=emb
            )
            db.add(db_chunk)

        doc.total_chunks = len(chunks)
        doc.processing_status = "completed"

        db.commit()

    except Exception as e:
        doc.processing_status = "failed"
        doc.processing_error = str(e)
        db.commit()
        raise

    finally:
        db.close()