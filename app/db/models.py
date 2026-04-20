from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import (
    String,
    Integer,
    ForeignKey,
    func,
    Text,
    Enum,
    text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY

from pgvector.sqlalchemy import Vector

from app.db.session import Base


# Document Model
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)

    file_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    total_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_chunks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    document_type: Mapped[str] = mapped_column(
        String,
        default="legal",
        server_default=text("'legal'"),
        nullable=False,
    )

    processing_status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed", name="processing_status_enum"),
        default="pending",
        server_default=text("'pending'"),
        nullable=False,
    )

    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # metadata is reserved → use metadata_
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        name="metadata",
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    chunks = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )


# ---------------------------
# Chunk Model
# ---------------------------
class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_header: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    chunk_type: Mapped[str] = mapped_column(
        String,
        server_default="text",
        nullable=False,
    )

    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Embedding vector (MiniLM = 384 dims)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(384),
        nullable=True,
    )

    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        name="metadata",
        nullable=True,
    )

    # Relationship
    document = relationship("Document", back_populates="chunks")


# ---------------------------
# Query Model
# ---------------------------
class Query(Base):
    __tablename__ = "queries"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    retrieved_chunk_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        nullable=True,
    )

    reranked_chunk_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        nullable=True,
    )

    model_used: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retrieval_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    generation_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now()
    )


# ---------------------------
# Evaluation Pair Model
# ---------------------------
class EvaluationPair(Base):
    __tablename__ = "evaluation_pairs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    query_text: Mapped[str] = mapped_column(Text, nullable=False)

    relevant_chunk_ids: Mapped[List[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now()
    )