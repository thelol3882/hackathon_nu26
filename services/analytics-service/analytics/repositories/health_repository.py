"""Health snapshot queries against health_snapshots table in TimescaleDB."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_latest_readings(session: AsyncSession, locomotive_id: str) -> list[dict]:
    """Latest sensor value per sensor — used for real-time health computation."""
    result = await session.execute(
        text("""
            SELECT DISTINCT ON (sensor_type) sensor_type, value, unit, locomotive_type
            FROM raw_telemetry
            WHERE locomotive_id = CAST(:loco_id AS uuid)
            ORDER BY sensor_type, time DESC
        """),
        {"loco_id": locomotive_id},
    )
    return [
        {
            "sensor_type": row.sensor_type,
            "value": row.value,
            "unit": row.unit,
            "locomotive_type": getattr(row, "locomotive_type", "TE33A"),
        }
        for row in result.fetchall()
    ]


async def get_snapshot_at(session: AsyncSession, locomotive_id: str, at: datetime) -> dict | None:
    """Health snapshot at or before a given time — for replay."""
    result = await session.execute(
        text("""
            SELECT score, category, top_factors, damage_penalty, calculated_at, locomotive_type
            FROM health_snapshots
            WHERE locomotive_id = CAST(:loco_id AS uuid) AND calculated_at <= :at
            ORDER BY calculated_at DESC LIMIT 1
        """),
        {"loco_id": locomotive_id, "at": at},
    )
    row = result.fetchone()
    if not row:
        return None
    return {
        "score": row.score,
        "category": row.category,
        "top_factors": row.top_factors,
        "damage_penalty": row.damage_penalty,
        "calculated_at": row.calculated_at,
        "locomotive_type": row.locomotive_type,
    }


# -- Report-oriented queries -----------------------------------------------


async def query_fleet_health(session: AsyncSession, start: datetime, end: datetime) -> dict:
    result = await session.execute(
        text("""
            WITH loco_scores AS (
                SELECT locomotive_id, AVG(score) AS avg_score
                FROM health_snapshots WHERE calculated_at BETWEEN :start AND :end
                GROUP BY locomotive_id
            )
            SELECT COUNT(*) AS total_locomotives, AVG(avg_score) AS fleet_avg,
                   MIN(avg_score) AS fleet_min, MAX(avg_score) AS fleet_max,
                   COUNT(*) FILTER (WHERE avg_score >= 80) AS healthy_count,
                   COUNT(*) FILTER (WHERE avg_score >= 50 AND avg_score < 80) AS warning_count,
                   COUNT(*) FILTER (WHERE avg_score < 50) AS critical_count
            FROM loco_scores
        """),
        {"start": start, "end": end},
    )
    row = result.fetchone()
    if not row or not row.total_locomotives:
        return {
            "total_locomotives": 0,
            "avg_score": 0,
            "min_score": 0,
            "max_score": 0,
            "healthy_count": 0,
            "warning_count": 0,
            "critical_count": 0,
        }
    return {
        "total_locomotives": int(row.total_locomotives),
        "avg_score": round(float(row.fleet_avg), 2),
        "min_score": round(float(row.fleet_min), 2),
        "max_score": round(float(row.fleet_max), 2),
        "healthy_count": int(row.healthy_count),
        "warning_count": int(row.warning_count),
        "critical_count": int(row.critical_count),
    }


async def query_worst_locomotives(session: AsyncSession, start: datetime, end: datetime, limit: int = 10) -> list[dict]:
    result = await session.execute(
        text("""
            SELECT locomotive_id, locomotive_type,
                   AVG(score) AS avg_score, MIN(score) AS min_score, MAX(score) AS max_score
            FROM health_snapshots
            WHERE calculated_at BETWEEN :start AND :end
            GROUP BY locomotive_id, locomotive_type
            ORDER BY AVG(score) ASC LIMIT :lim
        """),
        {"start": start, "end": end, "lim": limit},
    )
    return [
        {
            "locomotive_id": str(row.locomotive_id),
            "locomotive_type": row.locomotive_type,
            "serial_number": str(row.locomotive_id)[:12],
            "avg_score": round(float(row.avg_score), 2),
            "min_score": round(float(row.min_score), 2),
            "max_score": round(float(row.max_score), 2),
        }
        for row in result.fetchall()
    ]


async def query_health_trend(
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
            SELECT time_bucket('1 minute', calculated_at) AS bucket,
                   AVG(score) AS avg_score, MIN(score) AS min_score, MAX(score) AS max_score
            FROM health_snapshots
            WHERE calculated_at BETWEEN :start AND :end {where_loco}
            GROUP BY bucket ORDER BY bucket
        """),
        params,
    )
    return [
        {
            "time": row.bucket.isoformat(),
            "avg_score": round(float(row.avg_score), 2),
            "min_score": round(float(row.min_score), 2),
            "max_score": round(float(row.max_score), 2),
        }
        for row in result.fetchall()
    ]


async def query_latest_health(
    session: AsyncSession,
    locomotive_id: str | None,
    start: datetime,
    end: datetime,
) -> dict:
    params: dict = {"start": start, "end": end}
    where_loco = ""
    if locomotive_id:
        where_loco = "AND locomotive_id = CAST(:loco_id AS uuid)"
        params["loco_id"] = locomotive_id

    agg_result = await session.execute(
        text(f"""
            SELECT AVG(score) AS avg_score, MIN(score) AS min_score, MAX(score) AS max_score
            FROM health_snapshots WHERE calculated_at BETWEEN :start AND :end {where_loco}
        """),
        params,
    )
    agg = agg_result.fetchone()

    latest_result = await session.execute(
        text(f"""
            SELECT score, category, top_factors, damage_penalty
            FROM health_snapshots WHERE calculated_at BETWEEN :start AND :end {where_loco}
            ORDER BY calculated_at DESC LIMIT 1
        """),
        params,
    )
    latest = latest_result.fetchone()

    return {
        "avg_score": round(float(agg.avg_score), 2) if agg and agg.avg_score else 0.0,
        "min_score": round(float(agg.min_score), 2) if agg and agg.min_score else 0.0,
        "max_score": round(float(agg.max_score), 2) if agg and agg.max_score else 0.0,
        "category": latest.category if latest else "N/A",
        "top_factors": latest.top_factors if latest else [],
        "damage_penalty": round(float(latest.damage_penalty), 4) if latest else 0.0,
    }


async def query_fleet_latest_snapshots(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        text("""
            SELECT locomotive_id, locomotive_type, score, category FROM (
                SELECT locomotive_id, locomotive_type, score, category,
                       ROW_NUMBER() OVER (PARTITION BY locomotive_id ORDER BY calculated_at DESC) AS rn
                FROM health_snapshots
            ) sub WHERE rn = 1
        """)
    )
    return [
        {
            "locomotive_id": str(row.locomotive_id),
            "locomotive_type": row.locomotive_type,
            "score": float(row.score),
            "category": row.category,
        }
        for row in result.fetchall()
    ]
