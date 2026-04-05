"""Alert repository — PostgreSQL only."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.models.alert_entity import AlertRecord


async def find_many(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    severity: str | None = None,
    acknowledged: bool | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[dict]:
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
        " threshold_min, threshold_max, message, recommendation, timestamp, acknowledged"
        " FROM alert_events"
    )
    sql = f"{base} {where} ORDER BY timestamp DESC OFFSET :off LIMIT :lim"
    result = await session.execute(text(sql), params)
    return [dict(r) for r in result.mappings().all()]


async def find_by_id(session: AsyncSession, alert_id: str) -> dict | None:
    result = await session.execute(
        text(
            "SELECT id, locomotive_id, sensor_type, severity, value,"
            " threshold_min, threshold_max, message, recommendation, timestamp, acknowledged"
            " FROM alert_events WHERE id = CAST(:aid AS uuid)"
        ),
        {"aid": alert_id},
    )
    r = result.mappings().first()
    return dict(r) if r is not None else None


async def acknowledge(session: AsyncSession, alert_id: str) -> dict | None:
    await session.execute(
        text("UPDATE alert_events SET acknowledged = TRUE WHERE id = CAST(:aid AS uuid)"),
        {"aid": alert_id},
    )
    await session.execute(
        text("UPDATE alerts SET acknowledged = TRUE, acknowledged_at = NOW() WHERE id = CAST(:aid AS uuid)"),
        {"aid": alert_id},
    )
    await session.commit()
    return await find_by_id(session, alert_id)


async def bulk_insert(session: AsyncSession, records: list[AlertRecord]) -> int:
    if not records:
        return 0
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
                    "recommendation": r.recommendation,
                    "timestamp": r.timestamp,
                    "acknowledged": r.acknowledged,
                }
                for r in records
            ]
        )
        .on_conflict_do_nothing()
    )
    await session.execute(stmt)
    await session.commit()
    return len(records)
