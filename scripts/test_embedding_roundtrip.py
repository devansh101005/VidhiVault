import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import hashlib
import uuid

from sqlalchemy import select, text

from app.core.embedder import Embedder
from app.db.session import AsyncSessionLocal
from app.db.models import Document, Chunk


async def main():
    embedder = Embedder()
    print(f"Loaded embedder: {embedder.model_name} ({embedder.dimension}-dim)\n")

    test_text = "Section 302 IPC deals with the offense of murder and punishment thereof."
    embedding = embedder.embed_query(test_text)
    print(f"Generated embedding for test text.")
    print(f"  First 5 values: {[round(v, 6) for v in embedding[:5]]}")
    print(f"  Length: {len(embedding)}\n")

    async with AsyncSessionLocal() as db:
        unique_hash = "roundtrip_" + uuid.uuid4().hex
        doc = Document(
            title="Round-trip test doc",
            file_path="test/__nonexistent__.pdf",
            file_hash=unique_hash,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        print(f"Inserted Document id={doc.id}, status={doc.processing_status}")

        chunk = Chunk(
            document_id=doc.id,
            chunk_index=0,
            content=test_text,
            page_number=1,
            token_count=12,
            embedding=embedding,
        )
        db.add(chunk)
        await db.commit()
        await db.refresh(chunk)
        print(f"Inserted Chunk id={chunk.id}\n")

        result = await db.execute(select(Chunk).where(Chunk.id == chunk.id))
        reloaded = result.scalar_one()
        retrieved = list(reloaded.embedding)
        print(f"Reloaded embedding from DB.")
        print(f"  First 5 values: {[round(v, 6) for v in retrieved[:5]]}")
        print(f"  Length: {len(retrieved)}\n")

        max_diff = max(abs(a - b) for a, b in zip(embedding, retrieved))
        print(f"Max element-wise difference: {max_diff:.2e}")
        if max_diff < 1e-5:
            print("Round-trip PASS — vector survived intact.\n")
        else:
            print("Round-trip FAIL — values diverged.\n")

        sim_result = await db.execute(
            text(
                "SELECT id, 1 - (embedding <=> CAST(:q AS vector)) AS sim "
                "FROM chunks WHERE id = :cid"
            ),
            {"q": str(embedding), "cid": str(chunk.id)},
        )
        row = sim_result.one()
        print(f"pgvector cosine similarity (self vs self) = {row.sim:.6f}")
        print("Expected: ~1.0 (identical vectors).\n")

        await db.delete(doc)
        await db.commit()
        print(f"Cleaned up Document {doc.id} and cascaded Chunk.")


if __name__ == "__main__":
    asyncio.run(main())
