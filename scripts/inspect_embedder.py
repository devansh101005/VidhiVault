import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from app.core.embedder import Embedder


embedder = Embedder()
print(f"Model: {embedder.model_name}")
print(f"Dimension: {embedder.dimension}")
print(f"BGE-style prefix needed: {embedder.is_bge}")
print()

texts = [
    "What is the punishment for murder under the Indian Penal Code?",
    "Section 302 of the IPC prescribes the punishment for the offense of murder.",
    "How do I bake a chocolate cake at home?",
]

print("Embedding 3 texts...")
embeddings = embedder.embed_texts(texts)

print(f"\nResult: {len(embeddings)} vectors, each of length {len(embeddings[0])}")
print(f"First 5 values of vector[0]: {embeddings[0][:5]}")
print()

a = np.array(embeddings[0])
b = np.array(embeddings[1])
c = np.array(embeddings[2])

print("Cosine similarity scores (higher = more semantically similar):")
print(f"  murder query  <->  Section 302 sentence : {float(a @ b):.4f}")
print(f"  murder query  <->  cake recipe          : {float(a @ c):.4f}")
print()
print("Expected: first similarity should be clearly higher than the second.")
print()

query_emb = embedder.embed_query("What does Section 302 IPC say?")
print(f"Single-query embedding length: {len(query_emb)}")
print(f"First 5 values: {query_emb[:5]}")
print()

sample_chunks = [
    {"content": "Section 302 IPC defines murder and prescribes punishment.", "chunk_index": 0},
    {"content": "Section 420 IPC deals with cheating and fraudulent acts.", "chunk_index": 1},
]
with_embeddings = embedder.embed_chunks(sample_chunks)
print(f"embed_chunks added 'embedding' key to each chunk: {list(with_embeddings[0].keys())}")
print(f"Dimension stored on chunk[0]: {len(with_embeddings[0]['embedding'])}")
