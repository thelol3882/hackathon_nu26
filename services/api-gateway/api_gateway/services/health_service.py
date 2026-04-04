"""Health Index computation with DB→Redis config caching."""

from __future__ import annotations

import json

import redis.asyncio as redis
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.models.health_config_entity import HealthThreshold, HealthWeight
from shared.constants import DEFAULT_THRESHOLDS, HEALTH_WEIGHTS
from shared.log_codes import HEALTH_CONFIG_CACHED, HEALTH_CONFIG_SEEDED, HEALTH_CONFIG_UPDATED, HEALTH_COMPUTED, HEALTH_NO_DATA
from shared.observability import get_logger
from shared.schemas.health import ComponentHealth, HealthIndex

logger = get_logger(__name__)

_REDIS_THRESHOLDS_KEY = "health:thresholds"
_REDIS_WEIGHTS_KEY = "health:weights"


# --- Config models ---

class ThresholdConfig(BaseModel):
    sensor_type: str
    min_value: float
    max_value: float


class WeightConfig(BaseModel):
    sensor_type: str
    weight: float


# --- Startup: seed DB if empty, then cache to Redis ---

async def init_health_config(session: AsyncSession, redis_client: redis.Redis) -> None:
    """Load health config from DB into Redis. Seed DB from constants if empty."""
    # Seed thresholds
    result = await session.execute(select(HealthThreshold))
    existing = result.scalars().all()
    if not existing:
        for sensor, (lo, hi) in DEFAULT_THRESHOLDS.items():
            session.add(HealthThreshold(sensor_type=sensor, min_value=lo, max_value=hi))
        await session.commit()
        logger.info("Seeded health thresholds from defaults", code=HEALTH_CONFIG_SEEDED)

    # Seed weights
    result = await session.execute(select(HealthWeight))
    existing = result.scalars().all()
    if not existing:
        for sensor, w in HEALTH_WEIGHTS.items():
            session.add(HealthWeight(sensor_type=sensor, weight=w))
        await session.commit()
        logger.info("Seeded health weights from defaults", code=HEALTH_CONFIG_SEEDED)

    # Cache to Redis
    await _cache_config_to_redis(session, redis_client)


async def _cache_config_to_redis(session: AsyncSession, redis_client: redis.Redis) -> None:
    result = await session.execute(select(HealthThreshold))
    thresholds = {
        r.sensor_type: json.dumps({"min": r.min_value, "max": r.max_value})
        for r in result.scalars().all()
    }
    if thresholds:
        await redis_client.delete(_REDIS_THRESHOLDS_KEY)
        await redis_client.hset(_REDIS_THRESHOLDS_KEY, mapping=thresholds)

    result = await session.execute(select(HealthWeight))
    weights = {r.sensor_type: str(r.weight) for r in result.scalars().all()}
    if weights:
        await redis_client.delete(_REDIS_WEIGHTS_KEY)
        await redis_client.hset(_REDIS_WEIGHTS_KEY, mapping=weights)


# --- Read config from Redis ---

async def _get_thresholds(redis_client: redis.Redis) -> dict[str, tuple[float, float]]:
    raw = await redis_client.hgetall(_REDIS_THRESHOLDS_KEY)
    result = {}
    for sensor, val in raw.items():
        parsed = json.loads(val)
        result[sensor] = (parsed["min"], parsed["max"])
    return result or DEFAULT_THRESHOLDS


async def _get_weights(redis_client: redis.Redis) -> dict[str, float]:
    raw = await redis_client.hgetall(_REDIS_WEIGHTS_KEY)
    result = {sensor: float(w) for sensor, w in raw.items()}
    return result or HEALTH_WEIGHTS


# --- Health Index computation ---

def _compute_component_score(
    value: float, lo: float, hi: float
) -> float:
    """Compute score 0.0–1.0 based on how far value is from normal range."""
    if lo <= value <= hi:
        mid = (lo + hi) / 2
        span = (hi - lo) / 2
        if span == 0:
            return 1.0
        deviation = abs(value - mid) / span
        return max(0.0, 1.0 - deviation * 0.3)

    # Out of range: penalty proportional to how far out
    if value < lo:
        overshoot = (lo - value) / max(lo, 1.0)
    else:
        overshoot = (value - hi) / max(hi, 1.0)
    return max(0.0, 1.0 - overshoot)


async def get_health_index(
    session: AsyncSession,
    redis_client: redis.Redis,
    locomotive_id: str,
) -> HealthIndex:
    """Compute health index from latest sensor values."""
    thresholds = await _get_thresholds(redis_client)
    weights = await _get_weights(redis_client)

    query = text("""
        SELECT DISTINCT ON (sensor_type)
            sensor_type, value, unit
        FROM raw_telemetry
        WHERE locomotive_id = :loco_id::uuid
        ORDER BY sensor_type, time DESC
    """)
    result = await session.execute(query, {"loco_id": locomotive_id})
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No telemetry data found for this locomotive",
        )

    components: list[ComponentHealth] = []
    weighted_sum = 0.0
    total_weight = 0.0

    for row in rows:
        sensor = row.sensor_type
        lo, hi = thresholds.get(sensor, (0.0, 100.0))
        w = weights.get(sensor, 0.05)

        score = _compute_component_score(row.value, lo, hi)
        components.append(
            ComponentHealth(
                sensor_type=sensor,
                score=round(score, 3),
                latest_value=row.value,
                unit=row.unit,
            )
        )
        weighted_sum += score * w
        total_weight += w

    overall = round(weighted_sum / total_weight, 3) if total_weight > 0 else 0.0

    from datetime import datetime, timezone

    return HealthIndex(
        locomotive_id=locomotive_id,
        overall_score=overall,
        components=sorted(components, key=lambda c: c.score),
        calculated_at=datetime.now(timezone.utc),
    )


# --- Config CRUD ---

async def list_thresholds(session: AsyncSession) -> list[ThresholdConfig]:
    result = await session.execute(
        select(HealthThreshold).order_by(HealthThreshold.sensor_type)
    )
    return [
        ThresholdConfig(sensor_type=r.sensor_type, min_value=r.min_value, max_value=r.max_value)
        for r in result.scalars().all()
    ]


async def update_threshold(
    session: AsyncSession,
    redis_client: redis.Redis,
    sensor_type: str,
    min_value: float,
    max_value: float,
) -> ThresholdConfig:
    result = await session.execute(
        select(HealthThreshold).where(HealthThreshold.sensor_type == sensor_type)
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Threshold for '{sensor_type}' not found")

    entity.min_value = min_value
    entity.max_value = max_value
    await session.commit()

    # Update Redis cache
    await redis_client.hset(
        _REDIS_THRESHOLDS_KEY,
        sensor_type,
        json.dumps({"min": min_value, "max": max_value}),
    )

    return ThresholdConfig(sensor_type=sensor_type, min_value=min_value, max_value=max_value)


async def list_weights(session: AsyncSession) -> list[WeightConfig]:
    result = await session.execute(
        select(HealthWeight).order_by(HealthWeight.sensor_type)
    )
    return [
        WeightConfig(sensor_type=r.sensor_type, weight=r.weight)
        for r in result.scalars().all()
    ]


async def update_weight(
    session: AsyncSession,
    redis_client: redis.Redis,
    sensor_type: str,
    weight: float,
) -> WeightConfig:
    result = await session.execute(
        select(HealthWeight).where(HealthWeight.sensor_type == sensor_type)
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Weight for '{sensor_type}' not found")

    entity.weight = weight
    await session.commit()

    await redis_client.hset(_REDIS_WEIGHTS_KEY, sensor_type, str(weight))

    return WeightConfig(sensor_type=sensor_type, weight=weight)
