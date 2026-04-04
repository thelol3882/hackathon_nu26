"""Historical telemetry queries against TimescaleDB."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ALLOWED_BUCKETS = {"1 minute", "5 minutes", "15 minutes", "1 hour", "1 day"}
_DEFAULT_BUCKET = "1 minute"


class TelemetryBucket(BaseModel):
    bucket: datetime
    locomotive_id: str
    sensor_type: str
    avg_value: float
    min_value: float
    max_value: float
    last_value: float
    unit: str


class TelemetryRaw(BaseModel):
    time: datetime
    locomotive_id: str
    locomotive_type: str = ""
    sensor_type: str
    value: float
    filtered_value: float | None = None
    unit: str
    latitude: float | None = None
    longitude: float | None = None


def _build_where(
    params: dict,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    time_col: str = "time",
) -> str:
    """Build a WHERE clause dynamically, only including non-None filters."""
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


async def query_telemetry_bucketed(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    bucket_interval: str = _DEFAULT_BUCKET,
    offset: int = 0,
    limit: int = 50,
) -> list[TelemetryBucket]:
    if bucket_interval not in _ALLOWED_BUCKETS:
        bucket_interval = _DEFAULT_BUCKET

    params: dict = {"off": offset, "lim": limit}
    where = _build_where(params, locomotive_id=locomotive_id, sensor_type=sensor_type, start=start, end=end)

    # interval is safe to inline — validated against _ALLOWED_BUCKETS above
    query = text(f"""
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
        TelemetryBucket(
            bucket=row.bucket,
            locomotive_id=row.locomotive_id,
            sensor_type=row.sensor_type,
            avg_value=row.avg_value,
            min_value=row.min_value,
            max_value=row.max_value,
            last_value=row.last_value,
            unit=row.unit,
        )
        for row in result.fetchall()
    ]


async def query_telemetry_raw(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 200,
) -> list[TelemetryRaw]:
    params: dict = {"off": offset, "lim": limit}
    where = _build_where(params, locomotive_id=locomotive_id, sensor_type=sensor_type, start=start, end=end)

    query = text(f"""
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
        TelemetryRaw(
            time=row.time,
            locomotive_id=row.locomotive_id,
            locomotive_type=row.locomotive_type,
            sensor_type=row.sensor_type,
            value=row.value,
            filtered_value=row.filtered_value,
            unit=row.unit,
            latitude=row.latitude,
            longitude=row.longitude,
        )
        for row in result.fetchall()
    ]
