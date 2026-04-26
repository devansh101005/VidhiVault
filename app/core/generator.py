import asyncio
import httpx
from typing import List, Dict, Optional

from app.config import settings


class Generator:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://api.groq.com/openai/v1",
    ):
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self.base_url = base_url

        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not configured. Set it in .env."
            )

    MAX_CHARS_PER_CHUNK = 600

    def _parse_retry_after(self, response, fallback: float) -> float:
        header_val = response.headers.get("retry-after")
        if header_val:
            try:
                return float(header_val)
            except ValueError:
                pass
        import re
        match = re.search(r"try again in ([\d.]+)\s*s", response.text or "")
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return fallback

    def _format_context(self, chunks: List[Dict]) -> str:
        lines = []
        for idx, chunk in enumerate(chunks, start=1):
            title = chunk.get("document_title", "Unknown")
            page = chunk.get("page_number", "?")
            content = chunk["content"]
            if len(content) > self.MAX_CHARS_PER_CHUNK:
                content = content[: self.MAX_CHARS_PER_CHUNK].rstrip() + " ..."
            lines.append(
                f"[Source {idx}] (Document: {title}, Page: {page})\n{content}\n"
            )
        return "\n".join(lines)

    def _build_messages(self, query: str, chunks: List[Dict]) -> List[Dict]:
        context = self._format_context(chunks)

        system_prompt = (
            "You are a legal research assistant specialising in Indian law. "
            "Answer the user's question using ONLY the provided context.\n\n"
            "Rules:\n"
            "1. If the answer is not in the context, say exactly: "
            "'I cannot find this information in the provided documents.'\n"
            "2. Cite your sources inline using [Source N] format, where N is "
            "the source number from the context.\n"
            "3. Be precise. When quoting legal provisions, quote them verbatim.\n"
            "4. If multiple sources are relevant, cite all of them.\n"
            "5. Do not invent section numbers, case names, or legal principles "
            "not present in the context."
        )

        user_prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            f"Answer:"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    async def generate_answer(
        self,
        query: str,
        chunks: List[Dict],
    ) -> Dict:

        messages = self._build_messages(query, chunks)

        max_attempts = 3
        backoff_seconds = 2.0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(1, max_attempts + 1):
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.1,
                        "max_tokens": 512,
                    },
                )

                if response.status_code == 200:
                    break

                if response.status_code == 429 and attempt < max_attempts:
                    retry_after = self._parse_retry_after(response, backoff_seconds)
                    await asyncio.sleep(min(retry_after, 30.0))
                    continue

                raise RuntimeError(
                    f"Groq API error {response.status_code}: "
                    f"{response.text[:300]}"
                )

            data = response.json()

        answer_text = data["choices"][0]["message"]["content"]

        citations = []
        for idx, chunk in enumerate(chunks, start=1):
            citations.append({
                "source_number": idx,
                "chunk_id": str(chunk["chunk_id"]),
                "document_title": chunk.get("document_title", "Unknown"),
                "page_number": chunk.get("page_number"),
                "content_preview": chunk["content"][:200],
            })

        return {
            "answer": answer_text,
            "citations": citations,
        }
