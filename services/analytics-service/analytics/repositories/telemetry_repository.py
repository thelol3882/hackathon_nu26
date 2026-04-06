"""Telemetry queries against TimescaleDB hypertables and continuous aggregates.

Auto-selects between raw_telemetry and telemetry_{1min,15min,1hour} CAggs
based on the requested window span. CAggs use materialized_only=false
(migration a1f7c9d4e2b0) so results include live tail data. Raw queries
still apply time_bucket to keep the returned row count bounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class _AggregateLevel:
    source_table: str
    bucket_column: str
    label: str


_LEVELS = [
    (timedelta(minutes=15), _AggregateLevel("raw_telemetry", "time", "raw (bucketed)")),
    (timedelta(hours=2), _AggregateLevel("telemetry_1min", "bucket", "1min aggregate")),
    (timedelta(hours=24), _AggregateLevel("telemetry_15min", "bucket", "15min aggregate")),
    (timedelta(hours=999), _AggregateLevel("telemetry_1hour", "bucket", "1hour aggregate")),
]

# Explicit bucket_interval requests fall back to raw_telemetry; must stay within retention.
_RAW_RETENTION = timedelta(hours=72)

# Whitelist — these strings are interpolated into SQL, so no arbitrary text.
_ALLOWED_BUCKETS: dict[str, timedelta] = {
    "2 seconds": timedelta(seconds=2),
    "5 seconds": timedelta(seconds=5),
    "10 seconds": timedelta(seconds=10),
    "15 seconds": timedelta(seconds=15),
    "20 seconds": timedelta(seconds=20),
    "30 seconds": timedelta(seconds=30),
    "40 seconds": timedelta(seconds=40),
    "1 minute": timedelta(minutes=1),
    "5 minutes": timedelta(minutes=5),
    "10 minutes": timedelta(minutes=10),
    "15 minutes": timedelta(minutes=15),
    "30 minutes": timedelta(minutes=30),
    "1 hour": timedelta(hours=1),
}


def pick_level(start: datetime | None, end: datetime | None) -> _AggregateLevel:
    if start is None or end is None:
        return _LEVELS[0][1]
    span = end - start
    for threshold, level in _LEVELS:
        if span <= threshold:
            return level
    return _LEVELS[-1][1]


def _raw_bucket_size(span: timedelta) -> str:
    """Pick a bucket size for raw_telemetry keeping row count ~[30,120]."""
    minutes = span.total_seconds() / 60.0
    if minutes <= 2:
        return "2 seconds"
    if minutes <= 5:
        return "5 seconds"
    if minutes <= 10:
        return "10 seconds"
    return "15 seconds"


def _validate_bucket_interval(value: str | None) -> str | None:
    """Return a sanitized bucket_interval or None."""
    if not value:
        return None
    v = value.strip()
    if v in _ALLOWED_BUCKETS:
        return v
    logger.warning("Ignoring unsupported bucket_interval=%r", value)
    return None


# Fixed CAgg bucket sizes used for gap-detection thresholds.
_CAGG_BUCKET_SECONDS: dict[str, float] = {
    "telemetry_1min": 60.0,
    "telemetry_15min": 15 * 60.0,
    "telemetry_1hour": 60 * 60.0,
}


def _effective_bucket_seconds(source_table: str, bucket_size: str | None) -> float:
    """Bucket width in seconds for the given source/bucket, defaulting to 60s."""
    if source_table == "raw_telemetry" and bucket_size in _ALLOWED_BUCKETS:
        return _ALLOWED_BUCKETS[bucket_size].total_seconds()
    return _CAGG_BUCKET_SECONDS.get(source_table, 60.0)


def _ts_to_epoch(b) -> float:
    if isinstance(b, datetime):
        return b.timestamp()
    if isinstance(b, int | float):
        return float(b)
    return datetime.fromisoformat(str(b)).timestamp()


def _lttb(rows: list[dict], threshold: int) -> list[dict]:
    """Largest-Triangle-Three-Buckets downsampling that preserves peaks/valleys.
    Rows with avg_value=None are gap markers and pass through unchanged.
    """
    n = len(rows)
    if threshold <= 2 or n <= threshold:
        return rows

    sampled: list[dict] = []
    bucket_size = (n - 2) / (threshold - 2)

    sampled.append(rows[0])
    a = 0

    for i in range(threshold - 2):
        avg_x = 0.0
        avg_y = 0.0
        avg_count = 0
        next_start = int((i + 1) * bucket_size) + 1
        next_end = min(int((i + 2) * bucket_size) + 1, n)
        for j in range(next_start, next_end):
            v = rows[j].get("avg_value")
            if v is None:
                continue
            avg_x += _ts_to_epoch(rows[j]["bucket"])
            avg_y += float(v)
            avg_count += 1
        if avg_count == 0:
            # Full-gap bucket: preserve midpoint as a None marker.
            mid = rows[(next_start + next_end - 1) // 2]
            sampled.append(mid)
            a = (next_start + next_end - 1) // 2
            continue
        avg_x /= avg_count
        avg_y /= avg_count

        # Pick the bucket point forming the largest triangle with a and next centroid.
        cur_start = int(i * bucket_size) + 1
        cur_end = int((i + 1) * bucket_size) + 1
        a_x = _ts_to_epoch(rows[a]["bucket"])
        a_v = rows[a].get("avg_value")
        a_y = float(a_v) if a_v is not None else avg_y

        max_area = -1.0
        max_idx = cur_start
        for j in range(cur_start, cur_end):
            v = rows[j].get("avg_value")
            if v is None:
                # Always preserve gaps.
                max_idx = j
                break
            x = _ts_to_epoch(rows[j]["bucket"])
            area = abs((a_x - avg_x) * (float(v) - a_y) - (a_x - x) * (avg_y - a_y)) * 0.5
            if area > max_area:
                max_area = area
                max_idx = j

        sampled.append(rows[max_idx])
        a = max_idx

    sampled.append(rows[-1])
    return sampled


def _insert_gap_markers(
    rows: list[dict],
    bucket_size_seconds: float,
    *,
    gap_factor: float = 3.0,
) -> list[dict]:
    """Insert None-valued sentinel rows for gaps exceeding gap_factor × bucket size."""
    if not rows or bucket_size_seconds <= 0:
        return rows
    threshold = bucket_size_seconds * gap_factor
    out: list[dict] = [rows[0]]
    for prev, cur in pairwise(rows):
        prev_ts = _ts_to_epoch(prev["bucket"])
        cur_ts = _ts_to_epoch(cur["bucket"])
        if cur_ts - prev_ts > threshold:
            # Sentinel at midpoint so uPlot breaks the line while x stays monotonic.
            mid_ts = (prev_ts + cur_ts) / 2
            out.append(
                {
                    "bucket": datetime.fromtimestamp(mid_ts, tz=prev["bucket"].tzinfo)
                    if isinstance(prev["bucket"], datetime)
                    else mid_ts,
                    "locomotive_id": cur["locomotive_id"],
                    "sensor_type": cur["sensor_type"],
                    "avg_value": None,
                    "min_value": None,
                    "max_value": None,
                    "last_value": None,
                    "unit": cur.get("unit", ""),
                }
            )
        out.append(cur)
    return out


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


async def query_bucketed(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    sensor_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 500,
    bucket_interval: str | None = None,
    max_points: int = 0,
) -> tuple[list[dict], str]:
    requested_bucket = _validate_bucket_interval(bucket_interval)

    # Explicit bucket size forces raw_telemetry for high-resolution charts,
    # bypassing the span-based CAgg picker.
    use_raw = False
    bucket_size: str | None = None
    if requested_bucket is not None:
        # Fall back to CAgg if window predates raw retention.
        within_retention = start is None or (datetime.now(start.tzinfo) - start <= _RAW_RETENTION)
        if within_retention:
            use_raw = True
            bucket_size = requested_bucket

    if use_raw:
        level = _AggregateLevel("raw_telemetry", "time", f"raw ({bucket_size})")
    else:
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
        if bucket_size is None:
            span = (end - start) if (start and end) else timedelta(minutes=15)
            bucket_size = _raw_bucket_size(span)
        query = text(f"""
            SELECT time_bucket('{bucket_size}', time) AS bucket,
                   CAST(locomotive_id AS text) AS locomotive_id,
                   sensor_type,
                   avg(value)         AS avg_value,
                   min(value)         AS min_value,
                   max(value)         AS max_value,
                   last(value, time)  AS last_value,
                   max(unit)          AS unit
            FROM raw_telemetry {where}
            GROUP BY bucket, locomotive_id, sensor_type
            ORDER BY bucket ASC OFFSET :off LIMIT :lim
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

    rows = _insert_gap_markers(rows, _effective_bucket_seconds(level.source_table, bucket_size))

    if max_points and len(rows) > max_points:
        rows = _lttb(rows, max_points)

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
