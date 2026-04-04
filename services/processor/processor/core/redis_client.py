import redis.asyncio as redis

from processor.core.config import get_settings
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


async def publish_telemetry(loco_id: str, payload: str) -> None:
    await get_redis().publish(f"{TELEMETRY_CHANNEL}:{loco_id}", payload)


async def publish_alert(payload: str) -> None:
    await get_redis().publish(ALERT_CHANNEL, payload)
