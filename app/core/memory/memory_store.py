import logging

from redis import exceptions as redis_exceptions

from app.core.cache.redis_client import (
    redis_client,
    is_redis_available,
    MEMORY_TTL_SECONDS,
)
from app.core.memory.session_memory import SessionMemory

logger = logging.getLogger(__name__)

MEMORY_PREFIX = "drorbot:memory"

_fallback_store: dict[str, SessionMemory] = {}


async def get_session_memory(session_id: str):
    if await is_redis_available():
        try:
            raw = await redis_client.get(
                f"{MEMORY_PREFIX}:{session_id}"
            )
            if not raw:
                return None
            return SessionMemory.model_validate_json(raw)
        except (
            redis_exceptions.ConnectionError,
            redis_exceptions.TimeoutError,
        ) as e:
            logger.warning(
                "Redis read failed, falling back to in-memory",
                extra={"error": str(e)},
            )

    return _fallback_store.get(session_id)


async def save_session_memory(session_memory: SessionMemory):
    key = f"{MEMORY_PREFIX}:{session_memory.session_id}"

    if await is_redis_available():
        try:
            await redis_client.set(
                key,
                session_memory.model_dump_json(),
                ex=MEMORY_TTL_SECONDS,
            )
            return
        except (
            redis_exceptions.ConnectionError,
            redis_exceptions.TimeoutError,
        ) as e:
            logger.warning(
                "Redis write failed, falling back to in-memory",
                extra={"error": str(e)},
            )

    _fallback_store[session_memory.session_id] = session_memory


async def delete_session_memory(session_id: str):
    if await is_redis_available():
        try:
            await redis_client.delete(
                f"{MEMORY_PREFIX}:{session_id}"
            )
        except (
            redis_exceptions.ConnectionError,
            redis_exceptions.TimeoutError,
        ):
            pass

    _fallback_store.pop(session_id, None)
