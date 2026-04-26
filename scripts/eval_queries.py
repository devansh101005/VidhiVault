import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import time

import httpx

QUERIES = [
    "What is the punishment for theft under IPC?",
    "Section 379 IPC",
    "Section 302",
    "punishment for murder",
    "criminal conspiracy definition",
    "robbery deadly weapon",
    "culpable homicide not amounting to murder",
    "What constitutes abetment?",
    "kidnapping under IPC",
    "rape provisions Indian Penal Code",
    "bail provisions UAPA",
    "Article 21 right to life",
    "dowry death section",
    "extortion punishment",
    "theft by servant",
    "voluntarily causing hurt",
    "wrongful confinement",
    "breach of trust",
    "How do I bake a cake?",
    "what is the price of bitcoin?",
]


async def main():
    base_url = "http://localhost:8000"
    timeout = 60.0

    print(f"\n{'#':<3} {'ms':>6} {'cache':<5} {'status':<6} {'query':<50}")
    print("-" * 90)

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        for i, q in enumerate(QUERIES, start=1):
            start = time.perf_counter()
            try:
                r = await client.post("/api/v1/query", json={"query": q})
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                status = r.status_code
                if status == 200:
                    data = r.json()
                    cache = "Y" if data["metrics"]["cache_hit"] else "N"
                    print(f"{i:<3} {elapsed_ms:>6} {cache:<5} {status:<6} {q[:50]}")
                else:
                    print(f"{i:<3} {elapsed_ms:>6} {'-':<5} {status:<6} {q[:50]}")
                    print(f"     -> {r.text[:100]}")
            except Exception as e:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                print(f"{i:<3} {elapsed_ms:>6} {'-':<5} {'ERR':<6} {q[:50]}")
                print(f"     -> {type(e).__name__}: {str(e)[:100]}")
            await asyncio.sleep(12)

    print("\n--- Second pass (should be all cache hits) ---\n")
    print(f"{'#':<3} {'ms':>6} {'cache':<5} {'status':<6} {'query':<50}")
    print("-" * 90)

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        for i, q in enumerate(QUERIES, start=1):
            start = time.perf_counter()
            try:
                r = await client.post("/api/v1/query", json={"query": q})
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                status = r.status_code
                if status == 200:
                    data = r.json()
                    cache = "Y" if data["metrics"]["cache_hit"] else "N"
                    print(f"{i:<3} {elapsed_ms:>6} {cache:<5} {status:<6} {q[:50]}")
                else:
                    print(f"{i:<3} {elapsed_ms:>6} {'-':<5} {status:<6} {q[:50]}")
            except Exception as e:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                print(f"{i:<3} {elapsed_ms:>6} {'-':<5} {'ERR':<6} {q[:50]}")
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
