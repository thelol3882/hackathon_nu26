"""Alert repository — reads from alert_events in TimescaleDB via raw SQL."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
    await session.commit()
    return await find_by_id(session, alert_id)
