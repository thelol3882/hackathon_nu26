"""Health Index: cache from processor pub/sub, fallback to DB computation."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as redis
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.core.redis_client import cache_health, get_cached_health
from api_gateway.models.health_config_entity import HealthThreshold, HealthWeight
from shared.constants import DEFAULT_THRESHOLDS, HEALTH_CHANNEL, HEALTH_WEIGHTS, HI_CATEGORY_NORMAL, HI_CATEGORY_WARNING
from shared.log_codes import (
    HEALTH_CONFIG_SEEDED,
)
from shared.observability import get_logger
from shared.schemas.health import HealthFactor, HealthIndex
from shared.wire import decode as wire_decode

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
    thresholds = {r.sensor_type: json.dumps({"min": r.min_value, "max": r.max_value}) for r in result.scalars().all()}
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


# --- Background: cache health index from processor pub/sub ---


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
                if message["type"] != b"pmessage":
                    continue
                try:
                    channel: bytes = message["channel"]
                    # channel = b"health:live:<loco_id>"
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
                pass


# --- Health Index computation ---


def _compute_component_score(value: float, lo: float, hi: float) -> float:
    """Compute score 0.0-1.0 based on how far value is from normal range."""
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


def _categorize(score: float) -> str:
    if score >= HI_CATEGORY_NORMAL:
        return "Норма"
    if score >= HI_CATEGORY_WARNING:
        return "Внимание"
    return "Критично"


async def get_health_index(
    session: AsyncSession,
    redis_client: redis.Redis,
    locomotive_id: str,
) -> HealthIndex:
    """Return health index for a locomotive.

    Primary: read from Redis cache (populated by processor via health:live pub/sub).
    Fallback: compute from raw_telemetry if cache is empty (processor not running).
    """
    # Try cache first (populated by run_health_cache from processor pub/sub)
    cached = await get_cached_health(locomotive_id)
    if cached:
        try:
            return HealthIndex.model_validate(wire_decode(cached))
        except Exception:
            logger.warning("Failed to parse cached health index, falling back to DB", locomotive_id=locomotive_id)

    # Fallback: compute from DB
    thresholds = await _get_thresholds(redis_client)
    weights = await _get_weights(redis_client)

    query = text("""
        SELECT DISTINCT ON (sensor_type)
            sensor_type, value, unit, locomotive_type
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

    factors: list[tuple[float, HealthFactor]] = []  # (penalty, factor)
    total_penalty = 0.0
    locomotive_type = getattr(rows[0], "locomotive_type", "TE33A") if rows else "TE33A"

    for row in rows:
        sensor = row.sensor_type
        lo, hi = thresholds.get(sensor, (0.0, 100.0))
        w = weights.get(sensor, 0.05)

        score = _compute_component_score(row.value, lo, hi)
        penalty = (1.0 - score) * w
        total_penalty += penalty

        mid = (lo + hi) / 2
        span = (hi - lo) / 2 if hi != lo else 1.0
        deviation_pct = min(100.0, abs(row.value - mid) / span * 100) if span > 0 else 0.0

        factors.append(
            (
                penalty,
                HealthFactor(
                    sensor_type=sensor,
                    value=row.value,
                    unit=row.unit,
                    penalty=round(penalty, 4),
                    contribution_pct=0.0,  # filled below
                    deviation_pct=round(deviation_pct, 1),
                ),
            )
        )

    # Overall score: 100 minus weighted penalties scaled to 0-100
    overall = max(0.0, min(100.0, 100.0 - total_penalty * 100.0))

    # Top 5 factors by penalty, with contribution percentages
    factors.sort(key=lambda x: x[0], reverse=True)
    top_factors = []
    for penalty, factor in factors[:5]:
        if total_penalty > 0:
            factor.contribution_pct = round(penalty / total_penalty * 100, 1)
        top_factors.append(factor)

    return HealthIndex(
        locomotive_id=UUID(locomotive_id),
        locomotive_type=locomotive_type,
        overall_score=round(overall, 1),
        category=_categorize(overall),
        top_factors=top_factors,
        damage_penalty=0.0,  # Montsinger aging not computed in gateway
        calculated_at=datetime.now(UTC),
    )


# --- Config CRUD ---


async def list_thresholds(session: AsyncSession) -> list[ThresholdConfig]:
    result = await session.execute(select(HealthThreshold).order_by(HealthThreshold.sensor_type))
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
    result = await session.execute(select(HealthThreshold).where(HealthThreshold.sensor_type == sensor_type))
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
    result = await session.execute(select(HealthWeight).order_by(HealthWeight.sensor_type))
    return [WeightConfig(sensor_type=r.sensor_type, weight=r.weight) for r in result.scalars().all()]


async def update_weight(
    session: AsyncSession,
    redis_client: redis.Redis,
    sensor_type: str,
    weight: float,
) -> WeightConfig:
    result = await session.execute(select(HealthWeight).where(HealthWeight.sensor_type == sensor_type))
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Weight for '{sensor_type}' not found")

    entity.weight = weight
    await session.commit()

    await redis_client.hset(_REDIS_WEIGHTS_KEY, sensor_type, str(weight))

    return WeightConfig(sensor_type=sensor_type, weight=weight)
