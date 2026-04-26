from typing import List, Dict
from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        chunks: List[Dict],
        top_k: int = 5,
    ) -> List[Dict]:
        if not chunks:
            return []

        pairs = [(query, chunk["content"]) for chunk in chunks]

        scores = self.model.predict(
            pairs,
            batch_size=32,
            show_progress_bar=False,
        )

        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)

        reranked = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
        return reranked[:top_k]
