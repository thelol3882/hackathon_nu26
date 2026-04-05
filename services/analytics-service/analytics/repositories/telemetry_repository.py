"""Telemetry queries against TimescaleDB hypertables and continuous aggregates.

Historical queries auto-select the optimal data source (raw table or
continuous aggregate) based on the requested time range:

    < 15 min   -> raw_telemetry   (every second, max ~900 points)
    15m - 2h   -> telemetry_1min  (one per minute, max ~120 points)
    2h  - 24h  -> telemetry_15min (one per 15 min, max ~96 points)
    24h+       -> telemetry_1hour (one per hour)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.observability import get_logger

logger = get_logger(__name__)


# -- Aggregate level resolution -------------------------------------------


@dataclass(frozen=True)
class _AggregateLevel:
    source_table: str
    bucket_column: str
    label: str


_LEVELS = [
    (timedelta(minutes=15), _AggregateLevel("raw_telemetry", "time", "raw (1s)")),
    (timedelta(hours=2), _AggregateLevel("telemetry_1min", "bucket", "1min aggregate")),
    (timedelta(hours=24), _AggregateLevel("telemetry_15min", "bucket", "15min aggregate")),
    (timedelta(hours=999), _AggregateLevel("telemetry_1hour", "bucket", "1hour aggregate")),
]


def pick_level(start: datetime | None, end: datetime | None) -> _AggregateLevel:
    if start is None or end is None:
        return _LEVELS[0][1]
    span = end - start
    for threshold, level in _LEVELS:
        if span <= threshold:
            return level
    return _LEVELS[-1][1]


# -- WHERE clause builder -------------------------------------------------


def _build_where(
    params: dict,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    time_col: str = "time",
) -> str:
    clauses = []
    if locomotive_id:
        clauses.append("locomotive_id = CAST(:loco_id AS uuid)")
        params["loco_id"] = locomotive_id
    if sensor_type:
        clauses.append("sensor_type = :sensor")
        params["sensor"] = sensor_type
    if start:
        clauses.append(f"{time_col} >= :t_start")
        params["t_start"] = start
    if end:
        clauses.append(f"{time_col} <= :t_end")
        params["t_end"] = end
    return ("WHERE " + " AND ".join(clauses)) if clauses else ""


# -- Queries ---------------------------------------------------------------


async def query_bucketed(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 500,
) -> tuple[list[dict], str]:
    level = pick_level(start, end)
    time_col = level.bucket_column

    params: dict = {"off": offset, "lim": limit}
    where = _build_where(
        params,
        locomotive_id=locomotive_id,
        sensor_type=sensor_type,
        start=start,
        end=end,
        time_col=time_col,
    )

    if level.source_table == "raw_telemetry":
        query = text(f"""
            SELECT time AS bucket, CAST(locomotive_id AS text) AS locomotive_id,
                   sensor_type, value AS avg_value, value AS min_value,
                   value AS max_value, value AS last_value, unit
            FROM raw_telemetry {where}
            ORDER BY time ASC OFFSET :off LIMIT :lim
        """)
    else:
        query = text(f"""
            SELECT {time_col} AS bucket, CAST(locomotive_id AS text) AS locomotive_id,
                   sensor_type, avg_value, min_value, max_value, last_value, unit
            FROM {level.source_table} {where}
            ORDER BY {time_col} ASC OFFSET :off LIMIT :lim
        """)

    result = await session.execute(query, params)
    rows = [
        {
            "bucket": row.bucket,
            "locomotive_id": row.locomotive_id,
            "sensor_type": row.sensor_type,
            "avg_value": row.avg_value,
            "min_value": row.min_value,
            "max_value": row.max_value,
            "last_value": row.last_value,
            "unit": row.unit,
        }
        for row in result.fetchall()
    ]
    return rows, level.label


async def query_raw(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 200,
) -> list[dict]:
    params: dict = {"off": offset, "lim": limit}
    where = _build_where(params, locomotive_id=locomotive_id, sensor_type=sensor_type, start=start, end=end)

    result = await session.execute(
        text(f"""
            SELECT time, CAST(locomotive_id AS text) AS locomotive_id, locomotive_type,
                   sensor_type, value, filtered_value, unit, latitude, longitude
            FROM raw_telemetry {where}
            ORDER BY time DESC OFFSET :off LIMIT :lim
        """),
        params,
    )
    return [
        {
            "time": row.time,
            "locomotive_id": row.locomotive_id,
            "locomotive_type": row.locomotive_type,
            "sensor_type": row.sensor_type,
            "value": row.value,
            "filtered_value": row.filtered_value,
            "unit": row.unit,
            "latitude": row.latitude,
            "longitude": row.longitude,
        }
        for row in result.fetchall()
    ]


async def query_snapshot(
    session: AsyncSession,
    *,
    locomotive_id: str,
    at: datetime,
) -> list[dict]:
    result = await session.execute(
        text("""
            SELECT DISTINCT ON (sensor_type)
                CAST(locomotive_id AS text) AS locomotive_id, locomotive_type,
                sensor_type, value, filtered_value, unit, time AS timestamp,
                latitude, longitude
            FROM raw_telemetry
            WHERE locomotive_id = CAST(:loco_id AS uuid) AND time <= :at
            ORDER BY sensor_type, time DESC
        """),
        {"loco_id": locomotive_id, "at": at},
    )
    return [
        {
            "locomotive_id": row.locomotive_id,
            "locomotive_type": row.locomotive_type,
            "sensor_type": row.sensor_type,
            "value": row.value,
            "filtered_value": row.filtered_value,
            "unit": row.unit,
            "timestamp": row.timestamp,
            "latitude": row.latitude,
            "longitude": row.longitude,
        }
        for row in result.fetchall()
    ]


# -- Report-oriented queries (moved from report-service) ------------------


async def query_locomotive_type(session: AsyncSession, locomotive_id: str) -> str:
    result = await session.execute(
        text("SELECT locomotive_type FROM raw_telemetry WHERE locomotive_id = CAST(:loco_id AS uuid) LIMIT 1"),
        {"loco_id": locomotive_id},
    )
    row = result.fetchone()
    return row.locomotive_type if row else "N/A"


async def query_sensor_stats(
    session: AsyncSession,
    locomotive_id: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    params: dict = {"start": start, "end": end}
    where_loco = ""
    if locomotive_id:
        where_loco = "AND locomotive_id = CAST(:loco_id AS uuid)"
        params["loco_id"] = locomotive_id

    result = await session.execute(
        text(f"""
            SELECT sensor_type, unit,
                   AVG(filtered_value) AS avg_val, MIN(filtered_value) AS min_val,
                   MAX(filtered_value) AS max_val, STDDEV(filtered_value) AS stddev_val,
                   COUNT(*) AS sample_count
            FROM raw_telemetry
            WHERE time BETWEEN :start AND :end {where_loco}
            GROUP BY sensor_type, unit ORDER BY sensor_type
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


async def query_raw_for_anomalies(
    session: AsyncSession,
    locomotive_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    result = await session.execute(
        text("""
            SELECT sensor_type, filtered_value, time
            FROM raw_telemetry
            WHERE time BETWEEN :start AND :end AND locomotive_id = CAST(:loco_id AS uuid)
            ORDER BY sensor_type, time
        """),
        {"start": start, "end": end, "loco_id": locomotive_id},
    )
    return [
        {"sensor_type": row.sensor_type, "filtered_value": float(row.filtered_value), "time": row.time}
        for row in result.fetchall()
    ]


async def query_utilization(session: AsyncSession, locomotive_id: str | None, hours: int) -> dict:
    params: dict = {"hours": hours}
    where_loco = ""
    if locomotive_id:
        where_loco = "AND locomotive_id = CAST(:loco_id AS uuid)"
        params["loco_id"] = locomotive_id

    result = await session.execute(
        text(f"""
            SELECT COUNT(*) AS total_readings,
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
    return {
        "total_readings": total,
        "active_readings": active,
        "avg_speed": round(float(row.avg_speed), 2) if row and row.avg_speed else 0.0,
        "max_speed": round(float(row.max_speed), 2) if row and row.max_speed else 0.0,
    }
