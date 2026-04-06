"""Redis client for health index cache reads."""

from __future__ import annotations

import redis.asyncio as aioredis

from analytics.core.config import get_settings

_redis: aioredis.Redis | None = None
_redis_raw: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis, _redis_raw
    settings = get_settings()
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    _redis_raw = aioredis.from_url(settings.redis_url, decode_responses=False)


async def close_redis() -> None:
    global _redis, _redis_raw
    if _redis:
        await _redis.aclose()
        _redis = None
    if _redis_raw:
        await _redis_raw.aclose()
        _redis_raw = None


def get_redis() -> aioredis.Redis:
    if _redis is None:
        msg = "Redis not initialized."
        raise RuntimeError(msg)
    return _redis


def get_redis_raw() -> aioredis.Redis:
    if _redis_raw is None:
        msg = "Redis (raw) not initialized."
        raise RuntimeError(msg)
    return _redis_raw
