import os
import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"

MEMORY_TTL_SECONDS = int(
    os.getenv("MEMORY_TTL_SECONDS", "3600")
)

redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    max_connections=10,
    socket_connect_timeout=2,
    socket_timeout=3,
)


async def is_redis_available() -> bool:
    """
    Check if Redis is reachable.

    Returns False immediately when REDIS_ENABLED=false (env var).
    Catches all exception types — redis.asyncio.exceptions.ConnectionError
    inherits from RedisError, not from Python's built-in ConnectionError,
    so a broad except is required here.
    """
    if not REDIS_ENABLED:
        return False

    try:
        return await redis_client.ping()
    except Exception:
        logger.warning("Redis unavailable — falling back to in-memory alternatives")
        return False
