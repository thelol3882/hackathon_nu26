"""Telemetry repository — PostgreSQL/TimescaleDB only."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ALLOWED_BUCKETS = {"1 minute", "5 minutes", "10 minutes", "15 minutes", "30 minutes", "1 hour", "1 day"}
_DEFAULT_BUCKET = "1 minute"


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
    if locomotive_id is not None:
        clauses.append("locomotive_id = CAST(:loco_id AS uuid)")
        params["loco_id"] = locomotive_id
    if sensor_type is not None:
        clauses.append("sensor_type = :sensor")
        params["sensor"] = sensor_type
    if start is not None:
        clauses.append(f"{time_col} >= :t_start")
        params["t_start"] = start
    if end is not None:
        clauses.append(f"{time_col} <= :t_end")
        params["t_end"] = end
    return ("WHERE " + " AND ".join(clauses)) if clauses else ""


async def query_bucketed(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    bucket_interval: str = _DEFAULT_BUCKET,
    offset: int = 0,
    limit: int = 50,
) -> list[dict]:
    if bucket_interval not in _ALLOWED_BUCKETS:
        bucket_interval = _DEFAULT_BUCKET

    params: dict = {"off": offset, "lim": limit}
    where = _build_where(params, locomotive_id=locomotive_id, sensor_type=sensor_type, start=start, end=end)

    if start is not None:
        params["series_start"] = start
        if end is not None:
            params["series_end"] = end
        params.setdefault("loco_id", "")
        params.setdefault("sensor", "")

        series_end_expr = ":series_end" if end is not None else "NOW()"

        query = text(f"""  # noqa: S608
            WITH data AS (
                SELECT
                    time_bucket('{bucket_interval}', time) AS bucket,
                    CAST(locomotive_id AS text) AS locomotive_id,
                    sensor_type,
                    avg(value)  AS avg_value,
                    min(value)  AS min_value,
                    max(value)  AS max_value,
                    last(value, time) AS last_value,
                    unit
                FROM raw_telemetry
                {where}
                GROUP BY bucket, locomotive_id, sensor_type, unit
            ),
            series AS (
                SELECT time_bucket('{bucket_interval}', gs) AS bucket
                FROM generate_series(
                    CAST(:series_start AS timestamptz),
                    CAST({series_end_expr} AS timestamptz),
                    CAST('{bucket_interval}' AS interval)
                ) AS gs
            )
            SELECT
                s.bucket,
                COALESCE(d.locomotive_id, CAST(:loco_id AS text))  AS locomotive_id,
                COALESCE(d.sensor_type,   :sensor)    AS sensor_type,
                d.avg_value,
                d.min_value,
                d.max_value,
                d.last_value,
                COALESCE(d.unit, '')      AS unit
            FROM series s
            LEFT JOIN data d ON d.bucket = s.bucket
            ORDER BY s.bucket ASC
            OFFSET :off LIMIT :lim
        """)
    else:
        query = text(f"""  # noqa: S608
            SELECT
                time_bucket('{bucket_interval}', time) AS bucket,
                CAST(locomotive_id AS text) AS locomotive_id,
                sensor_type,
                avg(value)  AS avg_value,
                min(value)  AS min_value,
                max(value)  AS max_value,
                last(value, time) AS last_value,
                unit
            FROM raw_telemetry
            {where}
            GROUP BY bucket, locomotive_id, sensor_type, unit
            ORDER BY bucket ASC
            OFFSET :off LIMIT :lim
        """)

    result = await session.execute(query, params)
    return [
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

    query = text(f"""  # noqa: S608
        SELECT
            time, CAST(locomotive_id AS text) AS locomotive_id, locomotive_type, sensor_type,
            value, filtered_value, unit, latitude, longitude
        FROM raw_telemetry
        {where}
        ORDER BY time DESC
        OFFSET :off LIMIT :lim
    """)

    result = await session.execute(query, params)
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
                CAST(locomotive_id AS text) AS locomotive_id,
                locomotive_type,
                sensor_type,
                value,
                filtered_value,
                unit,
                time AS timestamp,
                latitude,
                longitude
            FROM raw_telemetry
            WHERE locomotive_id = CAST(:loco_id AS uuid)
              AND time <= :at
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
