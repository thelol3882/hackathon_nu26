"""Telemetry repository — PostgreSQL/TimescaleDB queries.

Historical queries auto-select the optimal data source (raw table or
continuous aggregate) based on the requested time range.  This keeps
response payloads consistently small (< 1000 points) regardless of
the window, which matters for frontend performance and network bandwidth.

    < 15 min   -> raw_telemetry   (every second, max ~900 points)
    15m - 2h   -> telemetry_1min  (one per minute, max ~120 points)
    2h  - 24h  -> telemetry_15min (one per 15 min, max ~96 points)
    24h - 72h  -> telemetry_1hour (one per hour, max ~72 points)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.observability import get_logger

logger = get_logger(__name__)


# ── Aggregate level resolution ────────────────────────────────────────


@dataclass(frozen=True)
class _AggregateLevel:
    """Describes one level of the continuous aggregate hierarchy."""

    source_table: str  # Table or materialized view to query
    bucket_column: str  # Column name for the time bucket
    needs_time_bucket: bool  # Whether to apply time_bucket() in the query
    label: str  # Human-readable label for logging/debugging


# Ordered from finest to coarsest resolution.
# The first level whose threshold exceeds the requested range is selected.
_LEVELS = [
    (
        timedelta(minutes=15),
        _AggregateLevel(
            source_table="raw_telemetry",
            bucket_column="time",
            needs_time_bucket=False,
            label="raw (1s)",
        ),
    ),
    (
        timedelta(hours=2),
        _AggregateLevel(
            source_table="telemetry_1min",
            bucket_column="bucket",
            needs_time_bucket=False,
            label="1min aggregate",
        ),
    ),
    (
        timedelta(hours=24),
        _AggregateLevel(
            source_table="telemetry_15min",
            bucket_column="bucket",
            needs_time_bucket=False,
            label="15min aggregate",
        ),
    ),
    (
        timedelta(hours=999),
        _AggregateLevel(
            source_table="telemetry_1hour",
            bucket_column="bucket",
            needs_time_bucket=False,
            label="1hour aggregate",
        ),
    ),
]


def pick_level(start: datetime | None, end: datetime | None) -> _AggregateLevel:
    """Select the optimal data source based on the requested time range.

    If start or end is None, defaults to raw_telemetry (safest fallback).
    """
    if start is None or end is None:
        return _LEVELS[0][1]  # raw

    span = end - start
    for threshold, level in _LEVELS:
        if span <= threshold:
            return level

    return _LEVELS[-1][1]  # coarsest


# ── WHERE clause builder ──────────────────────────────────────────────


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


# ── Bucketed query (auto-selects aggregate level) ─────────────────────


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
    """Query historical telemetry with automatic resolution selection.

    Returns a tuple of (rows, data_source_label) so the caller can
    expose the chosen level in a response header for debugging.
    """
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
        # Raw data: return individual rows with consistent column names.
        query = text(f"""
            SELECT
                time AS bucket,
                CAST(locomotive_id AS text) AS locomotive_id,
                sensor_type,
                value AS avg_value,
                value AS min_value,
                value AS max_value,
                value AS last_value,
                unit
            FROM raw_telemetry
            {where}
            ORDER BY time ASC
            OFFSET :off LIMIT :lim
        """)
    else:
        # Continuous aggregate: data is already bucketed.
        query = text(f"""
            SELECT
                {time_col} AS bucket,
                CAST(locomotive_id AS text) AS locomotive_id,
                sensor_type,
                avg_value,
                min_value,
                max_value,
                last_value,
                unit
            FROM {level.source_table}
            {where}
            ORDER BY {time_col} ASC
            OFFSET :off LIMIT :lim
        """)

    logger.debug("Telemetry query using %s", level.label)
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


# ── Raw query (always reads from raw_telemetry) ──────────────────────


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


# ── Snapshot query (always reads from raw_telemetry) ──────────────────


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
