from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def vector_search(
    db: AsyncSession,
    query_embedding: list[float],
    top_k: int = 20,
    document_id: str | None = None,
    document_type: str | None = None,
) -> list[dict]:

    # convert python list → string for pgvector
    embedding_str = str(query_embedding)

    base_query = """
        SELECT 
            c.id AS chunk_id,
            c.content,
            c.page_number,
            c.section_header,
            d.title AS document_title,
            1 - (c.embedding <=> :embedding) AS score
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
    """

    filters = []
    params = {"embedding": embedding_str, "top_k": top_k}

    if document_id:
        filters.append("c.document_id = :document_id")
        params["document_id"] = document_id

    if document_type:
        filters.append("d.document_type = :document_type")
        params["document_type"] = document_type

    if filters:
        base_query += " WHERE " + " AND ".join(filters)

    base_query += """
        ORDER BY c.embedding <=> :embedding
        LIMIT :top_k
    """

    result = await db.execute(text(base_query), params)

    rows = result.mappings().all()

    return [dict(row) for row in rows]


async def keyword_search(
    db: AsyncSession,
    query: str,
    top_k: int = 20,
    document_id: str | None = None,
    document_type: str | None = None,
) -> list[dict]:

    base_query = """
        SELECT
            c.id AS chunk_id,
            c.content,
            c.page_number,
            c.section_header,
            d.title AS document_title,
            ts_rank_cd(c.content_tsv, query) AS score
        FROM chunks c
        JOIN documents d ON c.document_id = d.id,
             plainto_tsquery('english', :query_text) query
        WHERE c.content_tsv @@ query
    """

    filters = []
    params = {"query_text": query, "top_k": top_k}

    if document_id:
        filters.append("c.document_id = :document_id")
        params["document_id"] = document_id

    if document_type:
        filters.append("d.document_type = :document_type")
        params["document_type"] = document_type

    if filters:
        base_query += " AND " + " AND ".join(filters)

    base_query += """
        ORDER BY score DESC
        LIMIT :top_k
    """

    result = await db.execute(text(base_query), params)
    rows = result.mappings().all()
    return [dict(row) for row in rows]


def reciprocal_rank_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    k: int = 60,
    top_k: int = 20,
) -> list[dict]:
    scores: dict = {}
    metadata: dict = {}

    for rank, result in enumerate(vector_results):
        chunk_id = result["chunk_id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        metadata[chunk_id] = result

    for rank, result in enumerate(keyword_results):
        chunk_id = result["chunk_id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        if chunk_id not in metadata:
            metadata[chunk_id] = result

    fused = []
    for chunk_id, rrf_score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        entry = dict(metadata[chunk_id])
        entry["score"] = rrf_score
        fused.append(entry)

    return fused[:top_k]


async def hybrid_search(
    db: AsyncSession,
    query: str,
    query_embedding: list[float],
    top_k_per_method: int = 20,
    top_k_final: int = 20,
    document_id: str | None = None,
    document_type: str | None = None,
) -> list[dict]:
    vec_results = await vector_search(
        db,
        query_embedding,
        top_k=top_k_per_method,
        document_id=document_id,
        document_type=document_type,
    )
    kw_results = await keyword_search(
        db,
        query,
        top_k=top_k_per_method,
        document_id=document_id,
        document_type=document_type,
    )
    return reciprocal_rank_fusion(
        vec_results, kw_results, k=60, top_k=top_k_final
    )
