from typing import List
from sentence_transformers import SentenceTransformer


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

        # BGE models need query prefix
        self.is_bge = "bge" in model_name.lower()

    def _format_query(self, query: str) -> str:
        if self.is_bge:
            return "Represent this sentence for searching relevant passages: " + query
        return query

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=32,                 # IMPORTANT (speed)
            show_progress_bar=True,
            normalize_embeddings=True      # cosine similarity works better
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        query = self._format_query(query)
        embedding = self.model.encode(
            query,
            normalize_embeddings=True
        )
        return embedding.tolist()

    def embed_chunks(self, chunks: List[dict]) -> List[dict]:
        texts = [c["content"] for c in chunks]
        embeddings = self.embed_texts(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk["embedding"] = emb
        return chunks