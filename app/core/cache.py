import hashlib
import json
from typing import Optional, Dict, Any

import redis.asyncio as redis

from app.config import settings


class QueryCache:
    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = 3600,
    ):
        self.redis_url = redis_url or settings.redis_url
        self.ttl_seconds = ttl_seconds
        self._client: Optional[redis.Redis] = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._client

    def _make_key(
        self,
        query: str,
        document_id: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> str:
        normalized = query.strip().lower()
        signature = f"{normalized}|{document_id or ''}|{document_type or ''}"
        digest = hashlib.sha256(signature.encode()).hexdigest()[:32]
        return f"qa:cache:{digest}"

    async def get(
        self,
        query: str,
        document_id: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        client = await self._get_client()
        key = self._make_key(query, document_id, document_type)
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(
        self,
        query: str,
        response: Dict[str, Any],
        document_id: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> None:
        client = await self._get_client()
        key = self._make_key(query, document_id, document_type)
        await client.setex(
            key,
            self.ttl_seconds,
            json.dumps(response, default=str),
        )
