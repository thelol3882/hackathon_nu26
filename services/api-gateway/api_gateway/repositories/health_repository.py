"""Health config repository (thresholds and weights in PostgreSQL)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.models.health_config_entity import HealthThreshold, HealthWeight
from shared.constants import DEFAULT_THRESHOLDS, HEALTH_WEIGHTS


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
