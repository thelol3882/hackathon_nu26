"""Telemetry repository — PostgreSQL/TimescaleDB only."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def query_locomotive_type(session: AsyncSession, loco_id: UUID) -> str:
    result = await session.execute(
        text("SELECT locomotive_type FROM raw_telemetry WHERE locomotive_id = :loco_id LIMIT 1"),
        {"loco_id": loco_id},
    )
    row = result.fetchone()
    return row.locomotive_type if row else "N/A"


async def query_sensor_stats(session: AsyncSession, loco_id: UUID | None, start: datetime, end: datetime) -> list[dict]:
    params: dict = {"start": start, "end": end}
    where_loco = ""
    if loco_id:
        where_loco = "AND locomotive_id = :loco_id"
        params["loco_id"] = loco_id

    result = await session.execute(
        text(f"""
            SELECT sensor_type, unit,
                   AVG(filtered_value) AS avg_val,
                   MIN(filtered_value) AS min_val,
                   MAX(filtered_value) AS max_val,
                   STDDEV(filtered_value) AS stddev_val,
                   COUNT(*) AS sample_count
            FROM raw_telemetry
            WHERE time BETWEEN :start AND :end {where_loco}
            GROUP BY sensor_type, unit
            ORDER BY sensor_type
        """),
        params,
    )
    return [
        {
            "sensor_type": row.sensor_type,
            "unit": row.unit,
            "avg": round(float(row.avg_val), 4) if row.avg_val else 0.0,
            "min": round(float(row.min_val), 4) if row.min_val else 0.0,
            "max": round(float(row.max_val), 4) if row.max_val else 0.0,
            "stddev": round(float(row.stddev_val), 4) if row.stddev_val else 0.0,
            "samples": int(row.sample_count),
        }
        for row in result.fetchall()
    ]


async def query_raw_for_anomalies(session: AsyncSession, loco_id: UUID, start: datetime, end: datetime) -> list[dict]:
    result = await session.execute(
        text("""
            SELECT sensor_type, filtered_value, time
            FROM raw_telemetry
            WHERE time BETWEEN :start AND :end AND locomotive_id = :loco_id
            ORDER BY sensor_type, time
        """),
        {"start": start, "end": end, "loco_id": loco_id},
    )
    return [
        {"sensor_type": row.sensor_type, "filtered_value": float(row.filtered_value), "time": row.time}
        for row in result.fetchall()
    ]


async def query_latest_sensor_readings(session: AsyncSession, locomotive_id: str) -> list[dict]:
    result = await session.execute(
        text("""
            SELECT DISTINCT ON (sensor_type) sensor_type, filtered_value, unit
            FROM raw_telemetry
            WHERE locomotive_id = :loco_id
            ORDER BY sensor_type, time DESC
        """),
        {"loco_id": locomotive_id},
    )
    return [
        {"sensor_type": row.sensor_type, "filtered_value": float(row.filtered_value), "unit": row.unit}
        for row in result.fetchall()
    ]


async def query_utilization(session: AsyncSession, locomotive_id: str | None, hours: int) -> dict:
    params: dict = {"hours": hours}
    where_loco = ""
    if locomotive_id:
        where_loco = "AND locomotive_id = :loco_id"
        params["loco_id"] = locomotive_id

    result = await session.execute(
        text(f"""
            SELECT
                COUNT(*) AS total_readings,
                COUNT(*) FILTER (WHERE filtered_value > 0) AS active_readings,
                AVG(filtered_value) AS avg_speed,
                MAX(filtered_value) AS max_speed
            FROM raw_telemetry
            WHERE sensor_type = 'speed_actual'
              AND time >= NOW() - MAKE_INTERVAL(hours => :hours)
              {where_loco}
        """),
        params,
    )
    row = result.fetchone()
    total = int(row.total_readings) if row and row.total_readings else 0
    active = int(row.active_readings) if row and row.active_readings else 0
    max_speed = getattr(row, "max_speed", None) if row else None
    return {
        "total_readings": total,
        "active_readings": active,
        "avg_speed": round(float(row.avg_speed), 2) if row and row.avg_speed else 0.0,
        "max_speed": round(float(max_speed), 2) if max_speed else 0.0,
    }
