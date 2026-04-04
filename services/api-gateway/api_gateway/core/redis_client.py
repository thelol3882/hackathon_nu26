import redis.asyncio as redis

from api_gateway.core.config import get_settings
from shared.constants import ALERT_CHANNEL, TELEMETRY_CHANNEL

_redis_pool: redis.Redis | None = None


async def init_redis() -> redis.Redis:
    global _redis_pool
    settings = get_settings()
    _redis_pool = redis.from_url(settings.redis_url, decode_responses=True)
    await _redis_pool.ping()
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


def get_redis() -> redis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_pool


async def subscribe_telemetry(loco_id: str):
    """Yields messages for a specific locomotive. Used by WebSocket handler."""
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(f"{TELEMETRY_CHANNEL}:{loco_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield message["data"]
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()


async def subscribe_alerts():
    """Yields alert messages. Used by WebSocket handler."""
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(ALERT_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield message["data"]
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()


# --- Health index cache ---

_HEALTH_CACHE_PREFIX = "health:cache"
_HEALTH_CACHE_TTL = 60  # seconds


async def cache_health(loco_id: str, data_json: str) -> None:
    """Cache the latest HealthIndex JSON for a locomotive."""
    await get_redis().set(f"{_HEALTH_CACHE_PREFIX}:{loco_id}", data_json, ex=_HEALTH_CACHE_TTL)


async def get_cached_health(loco_id: str) -> str | None:
    """Get cached HealthIndex JSON. Returns None if expired or missing."""
    return await get_redis().get(f"{_HEALTH_CACHE_PREFIX}:{loco_id}")
