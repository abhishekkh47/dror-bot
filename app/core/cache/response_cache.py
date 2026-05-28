import json
import logging
import os

import redis as redis_lib

from app.core.cache.redis_client import (
    redis_client,
    is_redis_available,
)

logger = logging.getLogger(__name__)

CACHE_TTL = int(
    os.getenv("RESPONSE_CACHE_TTL_SECONDS", "1800")
)


def get_cached_response(cache_key):
    if not is_redis_available():
        return None

    try:
        raw = redis_client.get(cache_key)
        if not raw:
            return None
        return json.loads(raw)
    except (
        redis_lib.ConnectionError,
        redis_lib.TimeoutError,
    ) as e:
        logger.warning(
            "Cache read failed",
            extra={"error": str(e)},
        )
        return None


def save_cached_response(cache_key, payload):
    if not is_redis_available():
        return

    try:
        redis_client.set(
            cache_key,
            json.dumps(payload),
            ex=CACHE_TTL,
        )
    except (
        redis_lib.ConnectionError,
        redis_lib.TimeoutError,
    ) as e:
        logger.warning(
            "Cache write failed",
            extra={"error": str(e)},
        )
