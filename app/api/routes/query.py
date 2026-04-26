import time
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Query as QueryModel
from app.api.schemas.query import QueryRequest, QueryResponse
from app.core.embedder import Embedder
from app.core.retriever import hybrid_search
from app.core.reranker import Reranker
from app.core.generator import Generator
from app.core.cache import QueryCache
from app.core.rate_limit import RateLimiter


router = APIRouter(prefix="/query", tags=["query"])

_embedder = Embedder()
_reranker = Reranker()
_generator = Generator()
_cache = QueryCache(ttl_seconds=3600)
_rate_limiter = RateLimiter(requests_per_minute=30)


@router.post("", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    client_ip = http_request.client.host if http_request.client else "unknown"

    # --- Rate limit check ---
    allowed, count = await _rate_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded ({count}/"
                f"{_rate_limiter.requests_per_minute} per minute). "
                "Try again in a minute."
            ),
        )

    total_start = time.perf_counter()

    doc_id_str = str(request.document_id) if request.document_id else None

    # --- Cache check ---
    cached = await _cache.get(
        request.query,
        document_id=doc_id_str,
        document_type=request.document_type,
    )
    if cached:
        cached["metrics"]["cache_hit"] = True
        cached["metrics"]["total_ms"] = int(
            (time.perf_counter() - total_start) * 1000
        )
        return QueryResponse(**cached)

    # --- Stage 1: embed + hybrid retrieve ---
    retrieval_start = time.perf_counter()
    embedding = _embedder.embed_query(request.query)
    candidates = await hybrid_search(
        db,
        request.query,
        embedding,
        top_k_per_method=20,
        top_k_final=20,
        document_id=doc_id_str,
        document_type=request.document_type,
    )
    retrieval_ms = int((time.perf_counter() - retrieval_start) * 1000)

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No relevant chunks found for this query.",
        )

    # --- Stage 2: rerank ---
    rerank_start = time.perf_counter()
    top_chunks = _reranker.rerank(request.query, candidates, top_k=5)
    rerank_ms = int((time.perf_counter() - rerank_start) * 1000)

    # --- Stage 3: generate ---
    gen_start = time.perf_counter()
    result = await _generator.generate_answer(request.query, top_chunks)
    gen_ms = int((time.perf_counter() - gen_start) * 1000)

    total_ms = int((time.perf_counter() - total_start) * 1000)

    # --- Persist query log ---
    query_record = QueryModel(
        query_text=request.query,
        response_text=result["answer"],
        retrieved_chunk_ids=[c["chunk_id"] for c in candidates],
        reranked_chunk_ids=[c["chunk_id"] for c in top_chunks],
        model_used=_generator.model,
        retrieval_latency_ms=retrieval_ms,
        generation_latency_ms=gen_ms,
        latency_ms=total_ms,
    )
    db.add(query_record)
    await db.commit()

    response_dict = {
        "answer": result["answer"],
        "citations": result["citations"],
        "metrics": {
            "retrieval_ms": retrieval_ms,
            "reranking_ms": rerank_ms,
            "generation_ms": gen_ms,
            "total_ms": total_ms,
            "chunks_retrieved": len(candidates),
            "chunks_after_rerank": len(top_chunks),
            "cache_hit": False,
        },
    }

    # --- Cache the response ---
    await _cache.set(
        request.query,
        response_dict,
        document_id=doc_id_str,
        document_type=request.document_type,
    )

    return QueryResponse(**response_dict)
