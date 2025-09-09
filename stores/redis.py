import redis.asyncio as aioredis
import os


class AsyncRedisCache:
    """
    Async Redis wrapper for storing processed email IDs.
    Works with AWS ElastiCache Redis (supports TLS).
    """

    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "rediss://localhost:6379/0")
        self.redis = aioredis.from_url(
            redis_url,
            decode_responses=True,
            ssl=True,
            socket_timeout=5
        )

    async def exists(self, key: str) -> bool:
        return await self.redis.exists(key) > 0

    async def set(self, key: str, value: str, ttl: int):
        """Store key with TTL"""
        await self.redis.set(key, value, ex=ttl)

    async def get(self, key: str):
        return await self.redis.get(key)
