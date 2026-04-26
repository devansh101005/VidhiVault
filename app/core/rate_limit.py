import time
from typing import Optional, Tuple

import redis.asyncio as redis

from app.config import settings


class RateLimiter:
    def __init__(
        self,
        redis_url: Optional[str] = None,
        requests_per_minute: int = 30,
    ):
        self.redis_url = redis_url or settings.redis_url
        self.requests_per_minute = requests_per_minute
        self._client: Optional[redis.Redis] = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._client

    async def is_allowed(self, identifier: str) -> Tuple[bool, int]:
        client = await self._get_client()
        minute = int(time.time() // 60)
        key = f"ratelimit:{identifier}:{minute}"

        count = await client.incr(key)
        if count == 1:
            await client.expire(key, 60)

        allowed = count <= self.requests_per_minute
        return allowed, count
