"""Alert CRUD and background persistence from Redis pub/sub."""

from __future__ import annotations

import asyncio
from datetime import datetime

import redis.asyncio as redis
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
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


# --- Background persistence task ---


_ALERT_BATCH_WINDOW = 0.2  # seconds — collect alerts then flush in one commit


async def run_alert_persistence(
    redis_client: redis.Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Subscribe to alerts:live and persist alerts to the DB in batches.

    Runs as a long-lived background asyncio task.
    """
    backoff = 1.0
    while True:
        pubsub = redis_client.pubsub()
        try:
            await pubsub.subscribe(ALERT_CHANNEL)
            backoff = 1.0
            logger.info("Alert persistence listener started", code=ALERT_LISTENER_STARTED)
            batch: list[AlertRecord] = []
            flush_handle: asyncio.TimerHandle | None = None
            loop = asyncio.get_event_loop()

            async def _flush() -> None:
                nonlocal batch
                if not batch:
                    return
                to_flush = batch
                batch = []
                try:
                    async with session_factory() as session:
                        stmt = (
                            pg_insert(AlertRecord)
                            .values(
                                [
                                    {
                                        "id": r.id,
                                        "locomotive_id": r.locomotive_id,
                                        "sensor_type": r.sensor_type,
                                        "severity": r.severity,
                                        "value": r.value,
                                        "threshold_min": r.threshold_min,
                                        "threshold_max": r.threshold_max,
                                        "message": r.message,
                                        "timestamp": r.timestamp,
                                        "acknowledged": r.acknowledged,
                                    }
                                    for r in to_flush
                                ]
                            )
                            .on_conflict_do_nothing()
                        )
                        await session.execute(stmt)
                        await session.commit()
                        logger.debug(
                            "Alerts persisted",
                            code=ALERT_PERSISTED,
                            count=len(to_flush),
                        )
                except Exception:
                    logger.exception("Failed to persist alerts batch", code=ALERT_PERSIST_FAILED)

            async for message in pubsub.listen():
                msg_type = message.get("type", b"")
                if msg_type not in (b"message", "message"):
                    continue
                try:
                    data = wire_decode(message["data"])
                    alert = AlertEvent.model_validate(data)
                    batch.append(
                        AlertRecord(
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
                    )
                    # Schedule flush after batch window if not already scheduled
                    if flush_handle is None or flush_handle.cancelled():
                        flush_handle = loop.call_later(
                            _ALERT_BATCH_WINDOW,
                            lambda: asyncio.ensure_future(_flush()),
                        )
                except Exception:
                    logger.exception("Failed to parse alert", code=ALERT_PERSIST_FAILED)
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


# --- CRUD ---


async def list_alerts(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    severity: str | None = None,
    acknowledged: bool | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[AlertEvent]:
    """Query alerts from alert_events (processor table — always has all alerts)."""
    clauses = []
    params: dict = {"off": offset, "lim": limit}

    if locomotive_id:
        clauses.append("locomotive_id = CAST(:loco_id AS uuid)")
        params["loco_id"] = locomotive_id
    if severity:
        clauses.append("severity = :severity")
        params["severity"] = severity
    if acknowledged is not None:
        clauses.append("acknowledged = :ack")
        params["ack"] = acknowledged
    if start:
        clauses.append("timestamp >= :t_start")
        params["t_start"] = start
    if end:
        clauses.append("timestamp <= :t_end")
        params["t_end"] = end

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    base = (
        "SELECT id, locomotive_id, sensor_type, severity, value,"
        " threshold_min, threshold_max, message, timestamp, acknowledged"
        " FROM alert_events"
    )
    sql = f"{base} {where} ORDER BY timestamp DESC OFFSET :off LIMIT :lim"
    result = await session.execute(text(sql), params)

    return [
        AlertEvent(
            id=r.id,
            locomotive_id=r.locomotive_id,
            sensor_type=r.sensor_type,
            severity=r.severity,
            value=float(r.value),
            threshold_min=float(r.threshold_min),
            threshold_max=float(r.threshold_max),
            message=r.message,
            timestamp=r.timestamp,
            acknowledged=r.acknowledged,
        )
        for r in result.mappings().all()
    ]


async def get_alert(session: AsyncSession, alert_id: str) -> AlertEvent:
    result = await session.execute(
        text(
            "SELECT id, locomotive_id, sensor_type, severity, value,"
            " threshold_min, threshold_max, message, timestamp, acknowledged"
            " FROM alert_events WHERE id = CAST(:aid AS uuid)"
        ),
        {"aid": alert_id},
    )
    r = result.mappings().first()
    if r is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertEvent(
        id=r["id"],
        locomotive_id=r["locomotive_id"],
        sensor_type=r["sensor_type"],
        severity=r["severity"],
        value=float(r["value"]),
        threshold_min=float(r["threshold_min"]),
        threshold_max=float(r["threshold_max"]),
        message=r["message"],
        timestamp=r["timestamp"],
        acknowledged=r["acknowledged"],
    )


async def acknowledge_alert(session: AsyncSession, alert_id: str) -> AlertEvent:
    # Update both alert tables: processor's alert_events and gateway's alerts
    await session.execute(
        text("UPDATE alert_events SET acknowledged = TRUE WHERE id = CAST(:aid AS uuid)"),
        {"aid": alert_id},
    )
    await session.execute(
        text("UPDATE alerts SET acknowledged = TRUE, acknowledged_at = NOW() WHERE id = CAST(:aid AS uuid)"),
        {"aid": alert_id},
    )
    await session.commit()

    result = await session.execute(
        text(
            "SELECT id, locomotive_id, sensor_type, severity, value,"
            " threshold_min, threshold_max, message, timestamp, acknowledged"
            " FROM alert_events WHERE id = CAST(:aid AS uuid)"
        ),
        {"aid": alert_id},
    )
    r = result.mappings().first()
    if r is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    logger.info("Alert acknowledged", code=ALERT_ACKNOWLEDGED, alert_id=alert_id)

    return AlertEvent(
        id=r["id"],
        locomotive_id=r["locomotive_id"],
        sensor_type=r["sensor_type"],
        severity=r["severity"],
        value=r["value"],
        threshold_min=r["threshold_min"],
        threshold_max=r["threshold_max"],
        message=r["message"],
        timestamp=r["timestamp"],
        acknowledged=r["acknowledged"],
    )
