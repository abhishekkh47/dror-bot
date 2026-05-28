import logging

from redis import exceptions as redis_exceptions

from app.core.cache.redis_client import (
    redis_client,
    is_redis_available,
)

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = 60
MAX_REQUESTS_PER_WINDOW = 30


async def is_rate_limited(session_id):
    """
    Simple session rate limiting.
    Fails open — if Redis is unavailable, allow the request.
    """

    if not await is_redis_available():
        return False

    try:
        key = f"drorbot:ratelimit:{session_id}"

        current = await redis_client.incr(key)

        if current == 1:
            await redis_client.expire(
                key,
                RATE_LIMIT_WINDOW,
            )
        return current > MAX_REQUESTS_PER_WINDOW
    except (
        redis_exceptions.ConnectionError,
        redis_exceptions.TimeoutError,
    ) as e:
        logger.warning(
            "Rate limiter failed, allowing request",
            extra={"error": str(e)},
        )
        return False
