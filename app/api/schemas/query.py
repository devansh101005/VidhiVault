from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    document_id: Optional[UUID] = None
    document_type: Optional[str] = None


class Citation(BaseModel):
    source_number: int
    chunk_id: str
    document_title: str
    page_number: Optional[int] = None
    content_preview: str


class QueryMetrics(BaseModel):
    retrieval_ms: int
    reranking_ms: int
    generation_ms: int
    total_ms: int
    chunks_retrieved: int
    chunks_after_rerank: int
    cache_hit: bool = False


class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    metrics: QueryMetrics
