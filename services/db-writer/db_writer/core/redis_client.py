"""Minimal Redis client for the db-writer service.

Only the raw (binary) client is needed — for XREADGROUP / XACK on streams.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from db_writer.core.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)

_redis_raw: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis_raw
    settings = get_settings()
    _redis_raw = aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=False,  # binary for msgpack payloads
    )
    logger.info("Redis client initialized (raw/binary)")


async def close_redis() -> None:
    global _redis_raw
    if _redis_raw:
        await _redis_raw.aclose()
        _redis_raw = None
        logger.info("Redis client closed")


def get_redis_raw() -> aioredis.Redis:
    assert _redis_raw is not None, "Redis not initialised — call init_redis() first"
    return _redis_raw
