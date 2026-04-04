import redis.asyncio as redis

from api_gateway.core.config import get_settings
from shared.constants import ALERT_CHANNEL, TELEMETRY_CHANNEL

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
    if _redis_pool is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_pool


def get_redis_raw() -> redis.Redis:
    if _redis_raw is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_raw


async def subscribe_telemetry(loco_id: str):
    pubsub = get_redis_raw().pubsub()
    await pubsub.subscribe(f"{TELEMETRY_CHANNEL}:{loco_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == b"message":
                yield message["data"]
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()


async def subscribe_alerts():
    pubsub = get_redis_raw().pubsub()
    await pubsub.subscribe(ALERT_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] == b"message":
                yield message["data"]
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()


# --- Health index cache (uses main string client) ---

_HEALTH_CACHE_PREFIX = "health:cache"
_HEALTH_CACHE_TTL = 60  # seconds


async def cache_health(loco_id: str, data: bytes) -> None:
    await get_redis_raw().set(f"{_HEALTH_CACHE_PREFIX}:{loco_id}", data, ex=_HEALTH_CACHE_TTL)


async def get_cached_health(loco_id: str) -> bytes | None:
    return await get_redis_raw().get(f"{_HEALTH_CACHE_PREFIX}:{loco_id}")
