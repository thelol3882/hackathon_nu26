"""Background task: cache health indices from Redis pub/sub."""

from __future__ import annotations

import asyncio

import redis.asyncio as redis

from api_gateway.core.redis_client import get_redis_raw
from shared.constants import HEALTH_CHANNEL
from shared.observability import get_logger

logger = get_logger(__name__)

_HEALTH_CACHE_PREFIX = "health:cache"
_HEALTH_CACHE_TTL = 60  # seconds


async def cache_health(loco_id: str, data: bytes) -> None:
    """Cache the latest HealthIndex (wire-encoded bytes) for a locomotive."""
    await get_redis_raw().set(f"{_HEALTH_CACHE_PREFIX}:{loco_id}", data, ex=_HEALTH_CACHE_TTL)


async def get_cached_health(loco_id: str) -> bytes | None:
    """Get cached HealthIndex as raw bytes. Returns None if expired or missing."""
    return await get_redis_raw().get(f"{_HEALTH_CACHE_PREFIX}:{loco_id}")


async def run_health_cache(redis_client: redis.Redis) -> None:
    """Subscribe to health:live:* and cache latest HealthIndex per locomotive."""
    backoff = 1.0
    while True:
        pubsub = redis_client.pubsub()
        try:
            await pubsub.psubscribe(f"{HEALTH_CHANNEL}:*")
            backoff = 1.0
            logger.info("Health cache listener started")
            async for message in pubsub.listen():
                if message["type"] != "pmessage":
                    continue
                try:
                    channel: bytes = message["channel"]
                    loco_id = channel.decode().rsplit(":", maxsplit=1)[-1]
                    await cache_health(loco_id, message["data"])
                except Exception:
                    logger.exception("Failed to cache health index")
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Health cache listener error, reconnecting", backoff_s=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
        finally:
            try:
                await pubsub.punsubscribe()
                await pubsub.aclose()
            except Exception:
                logger.debug("Failed to close pubsub during cleanup")
