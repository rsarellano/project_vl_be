import os
import redis.asyncio as redis

# Create a global Redis pool
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# The decode_responses=True parameter ensures that we get Python strings back instead of bytes
redis_client = redis.from_url(redis_url, decode_responses=True)

async def get_redis():
    """FastAPI dependency to get the Redis client."""
    return redis_client
