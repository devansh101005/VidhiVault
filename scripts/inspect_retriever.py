import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from app.core.embedder import Embedder
# from app.core.retriever import vector_search
# from app.core.retriever import keyword_search
from app.core.retriever import vector_search, keyword_search, hybrid_search
from app.db.session import AsyncSessionLocal
from app.core.reranker import Reranker



async def main():
    embedder = Embedder()
    reranker = Reranker()


    queries = [
        "What is the punishment for murder?",
        "Section 379",
        "robbery deadly weapon",
        "bail provisions",
        "culpable homicide not amounting to murder",
    ]

    async with AsyncSessionLocal() as db:
        for q in queries:
            print(f"\n{'=' * 70}")
            print(f"QUERY: {q}")
            print('=' * 70)

            embedding = embedder.embed_query(q)
            vec_results = await vector_search(db, embedding, top_k=5)
            kw_results = await keyword_search(db, q, top_k=5)
            hyb_results = await hybrid_search(
                db, q, embedding,
                top_k_per_method=20,
                top_k_final=5,
            )
            reranked = reranker.rerank(q, hyb_results, top_k=5)


            print("\n--- VECTOR (top 5) ---")
            for r in vec_results:
                print(f"  {r['score']:.4f}  p{r['page_number']}  {r['content'][:140]}")

            print("\n--- KEYWORD (top 5) ---")
            for r in kw_results:
                print(f"  {r['score']:.4f}  p{r['page_number']}  {r['content'][:140]}")

            print("\n--- HYBRID / RRF (top 5) ---")
            for r in hyb_results:
                print(f"  {r['score']:.4f}  p{r['page_number']}  {r['content'][:140]}")

            print("\n--- RERANKED (top 5) ---")
            for r in reranked:
                rrf = r["score"]
                rerank = r["rerank_score"]
                print(f"  rerank={rerank:+.4f}  rrf={rrf:.4f}  p{r['page_number']}  {r['content'][:140]}")




if __name__ == "__main__":
    asyncio.run(main())