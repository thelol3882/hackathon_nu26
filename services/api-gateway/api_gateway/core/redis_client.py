import redis.asyncio as redis

from api_gateway.core.config import get_settings

# Main client (decode_responses=True) for config cache, general string ops
_redis_pool: redis.Redis | None = None
# Raw client (decode_responses=False) for pub/sub — handles binary msgpack
_redis_raw: redis.Redis | None = None


async def init_redis() -> redis.Redis:
    global _redis_pool, _redis_raw
    settings = get_settings()
    _redis_pool = redis.from_url(settings.redis_url, decode_responses=True)
    _redis_raw = redis.from_url(settings.redis_url, decode_responses=False)
    await _redis_pool.ping()
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool, _redis_raw
    if _redis_raw:
        await _redis_raw.aclose()
        _redis_raw = None
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


def get_redis() -> redis.Redis:
    """Main Redis client (string-mode). For config cache, health cache, etc."""
    if _redis_pool is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_pool


def get_redis_raw() -> redis.Redis:
    """Raw Redis client (bytes-mode). For pub/sub that may carry msgpack."""
    if _redis_raw is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_raw
