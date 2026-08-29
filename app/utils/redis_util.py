import logging
from app.config.redis import _get_client

logger = logging.getLogger(__name__)

async def cache_set(key: str, value: str, ttl: int) -> None:
    try:
        await _get_client().set(key, value, ex=ttl)
    except Exception as e:
        logger.warning("Cache write failed for key=%s: %r", key, e)

async def cache_get(key: str) -> str | None:
    try:
        return await _get_client().get(key)
    except Exception as e:
        logger.warning("Cache read failed for key=%s: %r", key, e)
        return None