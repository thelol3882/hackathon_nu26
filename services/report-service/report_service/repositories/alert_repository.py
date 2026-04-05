"""Alert repository — PostgreSQL only."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def query_alerts(session: AsyncSession, loco_id: UUID | None, start: datetime, end: datetime) -> list[dict]:
    params: dict = {"start": start, "end": end}
    where_loco = ""
    if loco_id:
        where_loco = "AND locomotive_id = :loco_id"
        params["loco_id"] = loco_id

    result = await session.execute(
        text(f"""
            SELECT sensor_type, severity, value, threshold_min, threshold_max,
                   message, timestamp, acknowledged
            FROM alert_events
            WHERE timestamp BETWEEN :start AND :end {where_loco}
            ORDER BY timestamp DESC
            LIMIT 500
        """),
        params,
    )
    return [
        {
            "sensor_type": row.sensor_type,
            "severity": row.severity,
            "value": round(float(row.value), 4),
            "threshold_min": round(float(row.threshold_min), 4),
            "threshold_max": round(float(row.threshold_max), 4),
            "message": row.message,
            "timestamp": row.timestamp.isoformat(),
            "acknowledged": row.acknowledged,
        }
        for row in result.fetchall()
    ]


async def query_fleet_alert_summary(session: AsyncSession, start: datetime, end: datetime) -> dict:
    result = await session.execute(
        text("""
            SELECT severity, COUNT(*) AS cnt
            FROM alert_events
            WHERE timestamp BETWEEN :start AND :end
            GROUP BY severity
        """),
        {"start": start, "end": end},
    )
    by_severity = {}
    total = 0
    for row in result.fetchall():
        by_severity[row.severity] = int(row.cnt)
        total += int(row.cnt)
    return {"total": total, "by_severity": by_severity}
