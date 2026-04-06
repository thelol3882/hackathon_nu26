import redis.asyncio as redis

from processor.core.config import get_settings
from shared.constants import ALERT_CHANNEL, HEALTH_CHANNEL, TELEMETRY_CHANNEL
from shared.log_codes import INFRA_REDIS_CONNECTED
from shared.observability import get_logger

logger = get_logger(__name__)

_redis_pool: redis.Redis | None = None
# Binary client for pub/sub msgpack payloads.
_redis_raw: redis.Redis | None = None


async def init_redis() -> redis.Redis:
    global _redis_pool, _redis_raw
    settings = get_settings()
    _redis_pool = redis.from_url(settings.redis_url, decode_responses=True)
    _redis_raw = redis.from_url(settings.redis_url, decode_responses=False)
    await _redis_pool.ping()
    logger.info("Redis connected", code=INFRA_REDIS_CONNECTED, url=settings.redis_url)
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool, _redis_raw
    if _redis_raw:
        await _redis_raw.aclose()
        _redis_raw = None
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis connection closed")


def get_redis() -> redis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_pool


def get_redis_raw() -> redis.Redis:
    if _redis_raw is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_raw


async def publish_telemetry(loco_id: str, payload: bytes) -> None:
    """Publish wire-encoded telemetry to the live channel."""
    if _redis_raw is None:
        raise RuntimeError("Redis not initialized.")
    await _redis_raw.publish(f"{TELEMETRY_CHANNEL}:{loco_id}", payload)


async def publish_alert(payload: bytes) -> None:
    """Publish a wire-encoded AlertEvent to the global alert channel."""
    if _redis_raw is None:
        raise RuntimeError("Redis not initialized.")
    await _redis_raw.publish(ALERT_CHANNEL, payload)


async def publish_health(loco_id: str, payload: bytes) -> None:
    """Publish a wire-encoded HealthIndex to the live health channel."""
    if _redis_raw is None:
        raise RuntimeError("Redis not initialized.")
    await _redis_raw.publish(f"{HEALTH_CHANNEL}:{loco_id}", payload)
