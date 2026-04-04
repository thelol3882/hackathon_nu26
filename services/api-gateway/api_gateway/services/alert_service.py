"""Alert CRUD and background persistence from Redis pub/sub."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import redis.asyncio as redis
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api_gateway.models.alert_entity import AlertRecord
from shared.constants import ALERT_CHANNEL
from shared.log_codes import (
    ALERT_ACKNOWLEDGED,
    ALERT_LISTENER_ERROR,
    ALERT_LISTENER_STARTED,
    ALERT_PERSIST_FAILED,
    ALERT_PERSISTED,
)
from shared.observability import get_logger
from shared.schemas.alert import AlertEvent
from shared.wire import decode as wire_decode

logger = get_logger(__name__)


async def run_alert_persistence(
    redis_client: redis.Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Subscribe to alerts:live and persist each alert to DB. Runs as a background task."""
    backoff = 1.0
    while True:
        pubsub = redis_client.pubsub()
        try:
            await pubsub.subscribe(ALERT_CHANNEL)
            backoff = 1.0
            logger.info("Alert persistence listener started", code=ALERT_LISTENER_STARTED)
            async for message in pubsub.listen():
                msg_type = message.get("type", b"")
                if msg_type not in (b"message", "message"):
                    continue
                try:
                    data = wire_decode(message["data"])
                    alert = AlertEvent.model_validate(data)
                    async with session_factory() as session:
                        record = AlertRecord(
                            id=alert.id,
                            locomotive_id=alert.locomotive_id,
                            sensor_type=alert.sensor_type,
                            severity=alert.severity,
                            value=alert.value,
                            threshold_min=alert.threshold_min,
                            threshold_max=alert.threshold_max,
                            message=alert.message,
                            timestamp=alert.timestamp,
                            acknowledged=alert.acknowledged,
                        )
                        session.add(record)
                        await session.commit()
                        logger.info(
                            "Alert persisted",
                            code=ALERT_PERSISTED,
                            alert_id=str(alert.id),
                            locomotive_id=str(alert.locomotive_id),
                            severity=alert.severity,
                        )
                except Exception:
                    logger.exception("Failed to persist alert", code=ALERT_PERSIST_FAILED)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Alert listener error, reconnecting", code=ALERT_LISTENER_ERROR, backoff_s=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
        finally:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception:
                pass


async def list_alerts(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    severity: str | None = None,
    acknowledged: bool | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[AlertEvent]:
    stmt = select(AlertRecord).order_by(AlertRecord.timestamp.desc())

    if locomotive_id:
        stmt = stmt.where(AlertRecord.locomotive_id == locomotive_id)
    if severity:
        stmt = stmt.where(AlertRecord.severity == severity)
    if acknowledged is not None:
        stmt = stmt.where(AlertRecord.acknowledged == acknowledged)

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)

    return [
        AlertEvent(
            id=r.id,
            locomotive_id=r.locomotive_id,
            sensor_type=r.sensor_type,
            severity=r.severity,
            value=r.value,
            threshold_min=r.threshold_min,
            threshold_max=r.threshold_max,
            message=r.message,
            timestamp=r.timestamp,
            acknowledged=r.acknowledged,
        )
        for r in result.scalars().all()
    ]


async def get_alert(session: AsyncSession, alert_id: str) -> AlertEvent:
    result = await session.execute(select(AlertRecord).where(AlertRecord.id == alert_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertEvent(
        id=r.id,
        locomotive_id=r.locomotive_id,
        sensor_type=r.sensor_type,
        severity=r.severity,
        value=r.value,
        threshold_min=r.threshold_min,
        threshold_max=r.threshold_max,
        message=r.message,
        timestamp=r.timestamp,
        acknowledged=r.acknowledged,
    )


async def acknowledge_alert(session: AsyncSession, alert_id: str) -> AlertEvent:
    result = await session.execute(select(AlertRecord).where(AlertRecord.id == alert_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    r.acknowledged = True
    r.acknowledged_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(r)
    logger.info("Alert acknowledged", code=ALERT_ACKNOWLEDGED, alert_id=alert_id)

    return AlertEvent(
        id=r.id,
        locomotive_id=r.locomotive_id,
        sensor_type=r.sensor_type,
        severity=r.severity,
        value=r.value,
        threshold_min=r.threshold_min,
        threshold_max=r.threshold_max,
        message=r.message,
        timestamp=r.timestamp,
        acknowledged=r.acknowledged,
    )
