"""Health Index service — business logic, calls repository for DB access."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as redis
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.background.health_cache import get_cached_health
from api_gateway.repositories import health_repository
from shared.constants import DEFAULT_THRESHOLDS, HEALTH_WEIGHTS, HI_CATEGORY_NORMAL, HI_CATEGORY_WARNING
from shared.log_codes import HEALTH_CONFIG_SEEDED
from shared.observability import get_logger
from shared.schemas.health import HealthFactor, HealthIndex
from shared.wire import decode as wire_decode

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


def _compute_component_score(value: float, lo: float, hi: float) -> float:
    if lo <= value <= hi:
        mid = (lo + hi) / 2
        span = (hi - lo) / 2
        if span == 0:
            return 1.0
        deviation = abs(value - mid) / span
        return max(0.0, 1.0 - deviation * 0.3)
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
    cached = await get_cached_health(locomotive_id)
    if cached:
        try:
            return HealthIndex.model_validate(wire_decode(cached))
        except Exception:
            logger.warning("Failed to parse cached health index, falling back to DB", locomotive_id=locomotive_id)

    thresholds = await _get_thresholds(redis_client)
    weights = await _get_weights(redis_client)

    rows = await health_repository.get_latest_readings(session, locomotive_id)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No telemetry data found for this locomotive",
        )

    factors: list[tuple[float, HealthFactor]] = []
    total_penalty = 0.0
    locomotive_type = rows[0].get("locomotive_type", "TE33A") if rows else "TE33A"

    for row in rows:
        sensor = row["sensor_type"]
        lo, hi = thresholds.get(sensor, (0.0, 100.0))
        w = weights.get(sensor, 0.05)

        score = _compute_component_score(row["value"], lo, hi)
        penalty = (1.0 - score) * w
        total_penalty += penalty

        mid = (lo + hi) / 2
        span = (hi - lo) / 2 if hi != lo else 1.0
        deviation_pct = min(100.0, abs(row["value"] - mid) / span * 100) if span > 0 else 0.0

        factors.append(
            (
                penalty,
                HealthFactor(
                    sensor_type=sensor,
                    value=row["value"],
                    unit=row["unit"],
                    penalty=round(penalty, 4),
                    contribution_pct=0.0,
                    deviation_pct=round(deviation_pct, 1),
                ),
            )
        )

    overall = max(0.0, min(100.0, 100.0 - total_penalty * 100.0))

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
        damage_penalty=0.0,
        calculated_at=datetime.now(UTC),
    )


async def get_health_at(
    session: AsyncSession,
    locomotive_id: str,
    at: datetime,
) -> HealthIndex:
    row = await health_repository.get_snapshot_at(session, locomotive_id, at)
    if not row:
        raise HTTPException(status_code=404, detail="No health data at this time")

    top_factors = row["top_factors"] or []
    factor_list = top_factors if isinstance(top_factors, list) else []
    factors = [
        HealthFactor(
            sensor_type=f.get("sensor_type", ""),
            value=f.get("value", 0),
            unit=f.get("unit", ""),
            penalty=f.get("penalty", 0),
            contribution_pct=f.get("contribution_pct", 0),
            deviation_pct=f.get("deviation_pct", 0),
        )
        for f in factor_list
        if isinstance(f, dict)
    ]

    return HealthIndex(
        locomotive_id=UUID(locomotive_id),
        locomotive_type=row["locomotive_type"] or "TE33A",
        overall_score=round(float(row["score"]), 1),
        category=row["category"] or _categorize(float(row["score"])),
        top_factors=factors,
        damage_penalty=float(row["damage_penalty"] or 0),
        calculated_at=row["calculated_at"],
    )


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
