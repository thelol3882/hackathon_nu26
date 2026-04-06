"""Health config service — threshold and weight CRUD in PostgreSQL.

Health INDEX computation and queries now live in Analytics Service.
This module only manages the configuration (thresholds and weights)
stored in PostgreSQL and cached in Redis.
"""

from __future__ import annotations

import json

import redis.asyncio as redis
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.repositories import health_repository
from shared.log_codes import HEALTH_CONFIG_SEEDED
from shared.observability import get_logger

logger = get_logger(__name__)

_REDIS_THRESHOLDS_KEY = "health:thresholds"
_REDIS_WEIGHTS_KEY = "health:weights"


class ThresholdConfig(BaseModel):
    sensor_type: str
    min_value: float
    max_value: float


class WeightConfig(BaseModel):
    sensor_type: str
    weight: float


# --- Startup ---


async def init_health_config(session: AsyncSession, redis_client: redis.Redis) -> None:
    """Seed DB from constants if empty, then cache config to Redis."""
    if await health_repository.seed_thresholds(session):
        logger.info("Seeded health thresholds from defaults", code=HEALTH_CONFIG_SEEDED)
    if await health_repository.seed_weights(session):
        logger.info("Seeded health weights from defaults", code=HEALTH_CONFIG_SEEDED)
    await _cache_config_to_redis(session, redis_client)


async def _cache_config_to_redis(session: AsyncSession, redis_client: redis.Redis) -> None:
    thresholds = await health_repository.list_thresholds(session)
    mapping_t = {t.sensor_type: json.dumps({"min": t.min_value, "max": t.max_value}) for t in thresholds}
    if mapping_t:
        await redis_client.delete(_REDIS_THRESHOLDS_KEY)
        await redis_client.hset(_REDIS_THRESHOLDS_KEY, mapping=mapping_t)

    weights = await health_repository.list_weights(session)
    mapping_w = {w.sensor_type: str(w.weight) for w in weights}
    if mapping_w:
        await redis_client.delete(_REDIS_WEIGHTS_KEY)
        await redis_client.hset(_REDIS_WEIGHTS_KEY, mapping=mapping_w)


# --- Config CRUD ---


async def list_thresholds(session: AsyncSession) -> list[ThresholdConfig]:
    entities = await health_repository.list_thresholds(session)
    return [ThresholdConfig(sensor_type=e.sensor_type, min_value=e.min_value, max_value=e.max_value) for e in entities]


async def update_threshold(
    session: AsyncSession,
    redis_client: redis.Redis,
    sensor_type: str,
    min_value: float,
    max_value: float,
) -> ThresholdConfig:
    entity = await health_repository.update_threshold(session, sensor_type, min_value, max_value)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Threshold for '{sensor_type}' not found")
    await redis_client.hset(
        _REDIS_THRESHOLDS_KEY,
        sensor_type,
        json.dumps({"min": min_value, "max": max_value}),
    )
    return ThresholdConfig(sensor_type=sensor_type, min_value=min_value, max_value=max_value)


async def list_weights(session: AsyncSession) -> list[WeightConfig]:
    entities = await health_repository.list_weights(session)
    return [WeightConfig(sensor_type=e.sensor_type, weight=e.weight) for e in entities]


async def update_weight(
    session: AsyncSession,
    redis_client: redis.Redis,
    sensor_type: str,
    weight: float,
) -> WeightConfig:
    entity = await health_repository.update_weight(session, sensor_type, weight)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Weight for '{sensor_type}' not found")
    await redis_client.hset(_REDIS_WEIGHTS_KEY, sensor_type, str(weight))
    return WeightConfig(sensor_type=sensor_type, weight=weight)
