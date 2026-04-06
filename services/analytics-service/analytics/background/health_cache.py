"""Cache latest HealthIndex per locomotive from health:live:* pub/sub.

GetCurrentHealth checks this short-TTL cache before falling back to TimescaleDB.
"""

from __future__ import annotations

import asyncio

import redis.asyncio as aioredis

from shared.constants import HEALTH_CHANNEL
from shared.observability import get_logger

logger = get_logger(__name__)

_HEALTH_CACHE_PREFIX = "health:cache"
_HEALTH_CACHE_TTL = 60


async def get_cached_health(redis_raw: aioredis.Redis, loco_id: str) -> bytes | None:
    return await redis_raw.get(f"{_HEALTH_CACHE_PREFIX}:{loco_id}")


async def run_health_cache(redis_raw: aioredis.Redis) -> None:
    """Subscribe to health:live:* and cache the latest HealthIndex per locomotive."""
    backoff = 1.0
    while True:
        pubsub = redis_raw.pubsub()
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
                    await redis_raw.set(
                        f"{_HEALTH_CACHE_PREFIX}:{loco_id}",
                        message["data"],
                        ex=_HEALTH_CACHE_TTL,
                    )
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
