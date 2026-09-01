import hashlib
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.redis_url, decode_responses=True, socket_connect_timeout=2
            )
            await _redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis not available: {e}. Caching disabled.")
            _redis_client = None
    return _redis_client


def make_cache_key(payload: dict) -> str:
    """Create a deterministic SHA-256 cache key from a request payload."""
    canonical = json.dumps(payload, sort_keys=True)
    return f"chat:{hashlib.sha256(canonical.encode()).hexdigest()}"


async def get_cached(key: str) -> Optional[str]:
    r = await get_redis()
    if not r:
        return None
    try:
        return await r.get(key)
    except Exception:
        return None


async def set_cached(key: str, value: str) -> None:
    r = await get_redis()
    if not r:
        return
    try:
        await r.set(key, value, ex=settings.cache_ttl)
    except Exception as e:
        logger.warning(f"Failed to set cache: {e}")


async def check_redis_health() -> bool:
    r = await get_redis()
    if not r:
        return False
    try:
        await r.ping()
        return True
    except Exception:
        return False
