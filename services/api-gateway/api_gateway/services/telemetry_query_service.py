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

    query = text("""
        SELECT
            time_bucket(:interval, time) AS bucket,
            CAST(locomotive_id AS text),
            sensor_type,
            avg(value)  AS avg_value,
            min(value)  AS min_value,
            max(value)  AS max_value,
            last(value, time) AS last_value,
            unit
        FROM raw_telemetry
        WHERE (:loco_id IS NULL OR locomotive_id = CAST(:loco_id AS uuid))
          AND (:sensor  IS NULL OR sensor_type  = :sensor)
          AND (:t_start IS NULL OR time >= :t_start)
          AND (:t_end   IS NULL OR time <= :t_end)
        GROUP BY bucket, locomotive_id, sensor_type, unit
        ORDER BY bucket DESC
        OFFSET :off LIMIT :lim
    """)

    result = await session.execute(
        query,
        {
            "interval": bucket_interval,
            "loco_id": locomotive_id,
            "sensor": sensor_type,
            "t_start": start,
            "t_end": end,
            "off": offset,
            "lim": limit,
        },
    )

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
    query = text("""
        SELECT
            time, CAST(locomotive_id AS text), locomotive_type, sensor_type,
            value, filtered_value, unit, latitude, longitude
        FROM raw_telemetry
        WHERE (:loco_id IS NULL OR locomotive_id = CAST(:loco_id AS uuid))
          AND (:sensor  IS NULL OR sensor_type  = :sensor)
          AND (:t_start IS NULL OR time >= :t_start)
          AND (:t_end   IS NULL OR time <= :t_end)
        ORDER BY time DESC
        OFFSET :off LIMIT :lim
    """)

    result = await session.execute(
        query,
        {
            "loco_id": locomotive_id,
            "sensor": sensor_type,
            "t_start": start,
            "t_end": end,
            "off": offset,
            "lim": limit,
        },
    )

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
