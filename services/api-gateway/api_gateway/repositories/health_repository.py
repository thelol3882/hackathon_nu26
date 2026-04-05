"""Health repository — split across two databases.

Config queries (thresholds, weights, seed) use AppSession (PostgreSQL).
Telemetry queries (latest readings, health snapshots) use TsSession (TimescaleDB).
Callers are responsible for passing the correct session.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.models.health_config_entity import HealthThreshold, HealthWeight
from shared.constants import DEFAULT_THRESHOLDS, HEALTH_WEIGHTS


async def get_latest_readings(session: AsyncSession, locomotive_id: str) -> list[dict]:
    result = await session.execute(
        text("""
            SELECT DISTINCT ON (sensor_type)
                sensor_type, value, unit, locomotive_type
            FROM raw_telemetry
            WHERE locomotive_id = CAST(:loco_id AS uuid)
            ORDER BY sensor_type, time DESC
        """),
        {"loco_id": locomotive_id},
    )
    return [
        {
            "sensor_type": row.sensor_type,
            "value": row.value,
            "unit": row.unit,
            "locomotive_type": getattr(row, "locomotive_type", "TE33A"),
        }
        for row in result.fetchall()
    ]


async def get_snapshot_at(session: AsyncSession, locomotive_id: str, at: datetime) -> dict | None:
    result = await session.execute(
        text("""
            SELECT score, category, top_factors, damage_penalty, calculated_at, locomotive_type
            FROM health_snapshots
            WHERE locomotive_id = CAST(:loco_id AS uuid)
              AND calculated_at <= :at
            ORDER BY calculated_at DESC
            LIMIT 1
        """),
        {"loco_id": locomotive_id, "at": at},
    )
    row = result.fetchone()
    if not row:
        return None
    return {
        "score": row.score,
        "category": row.category,
        "top_factors": row.top_factors,
        "damage_penalty": row.damage_penalty,
        "calculated_at": row.calculated_at,
        "locomotive_type": row.locomotive_type,
    }


async def list_thresholds(session: AsyncSession) -> list[HealthThreshold]:
    result = await session.execute(select(HealthThreshold).order_by(HealthThreshold.sensor_type))
    return list(result.scalars().all())


async def list_weights(session: AsyncSession) -> list[HealthWeight]:
    result = await session.execute(select(HealthWeight).order_by(HealthWeight.sensor_type))
    return list(result.scalars().all())


async def update_threshold(
    session: AsyncSession, sensor_type: str, min_value: float, max_value: float
) -> HealthThreshold | None:
    result = await session.execute(select(HealthThreshold).where(HealthThreshold.sensor_type == sensor_type))
    entity = result.scalar_one_or_none()
    if entity is None:
        return None
    entity.min_value = min_value
    entity.max_value = max_value
    await session.commit()
    return entity


async def update_weight(session: AsyncSession, sensor_type: str, weight: float) -> HealthWeight | None:
    result = await session.execute(select(HealthWeight).where(HealthWeight.sensor_type == sensor_type))
    entity = result.scalar_one_or_none()
    if entity is None:
        return None
    entity.weight = weight
    await session.commit()
    return entity


async def seed_thresholds(session: AsyncSession) -> bool:
    """Seed default thresholds if table is empty. Returns True if seeded."""
    result = await session.execute(select(HealthThreshold))
    if result.scalars().first() is not None:
        return False
    for sensor, (lo, hi) in DEFAULT_THRESHOLDS.items():
        session.add(HealthThreshold(sensor_type=sensor, min_value=lo, max_value=hi))
    await session.commit()
    return True


async def seed_weights(session: AsyncSession) -> bool:
    """Seed default weights if table is empty. Returns True if seeded."""
    result = await session.execute(select(HealthWeight))
    if result.scalars().first() is not None:
        return False
    for sensor, w in HEALTH_WEIGHTS.items():
        session.add(HealthWeight(sensor_type=sensor, weight=w))
    await session.commit()
    return True
