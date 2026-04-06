"""Raw (binary) Redis client for pub/sub msgpack payloads and GETDEL tickets."""

from __future__ import annotations

import redis.asyncio as aioredis

from shared.observability import get_logger
from ws_server.core.config import get_settings

logger = get_logger(__name__)

_redis_raw: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis_raw
    settings = get_settings()
    _redis_raw = aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=False,
    )
    await _redis_raw.ping()
    logger.info("Redis client initialized")


async def close_redis() -> None:
    global _redis_raw
    if _redis_raw:
        await _redis_raw.aclose()
        _redis_raw = None
        logger.info("Redis client closed")


def get_redis_raw() -> aioredis.Redis:
    if _redis_raw is None:
        raise RuntimeError("Redis not initialized; call init_redis() first")
    return _redis_raw
