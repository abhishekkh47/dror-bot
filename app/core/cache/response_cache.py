import json
import logging
import os

from redis import exceptions as redis_exceptions

from app.core.cache.redis_client import (
    redis_client,
    is_redis_available,
)

logger = logging.getLogger(__name__)

CACHE_TTL = int(
    os.getenv("RESPONSE_CACHE_TTL_SECONDS", "1800")
)


async def get_cached_response(cache_key):
    if not await is_redis_available():
        return None

    try:
        raw = await redis_client.get(cache_key)
        if not raw:
            return None
        return json.loads(raw)
    except (
        redis_exceptions.ConnectionError,
        redis_exceptions.TimeoutError,
    ) as e:
        logger.warning(
            "Cache read failed",
            extra={"error": str(e)},
        )
        return None


async def save_cached_response(cache_key, payload):
    if not await is_redis_available():
        return

    try:
        await redis_client.set(
            cache_key,
            json.dumps(payload),
            ex=CACHE_TTL,
        )
    except (
        redis_exceptions.ConnectionError,
        redis_exceptions.TimeoutError,
    ) as e:
        logger.warning(
            "Cache write failed",
            extra={"error": str(e)},
        )
