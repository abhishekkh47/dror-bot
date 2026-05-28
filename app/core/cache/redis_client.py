import os
import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

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
    socket_connect_timeout=3,
    socket_timeout=5,
    retry_on_timeout=True,
)


async def is_redis_available():
    try:
        return await redis_client.ping()
    except (ConnectionError, TimeoutError, OSError):
        logger.warning("Redis unavailable")
        return False
