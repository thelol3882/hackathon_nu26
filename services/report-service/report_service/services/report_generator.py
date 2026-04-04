"""Orchestrates report generation: query TimescaleDB -> calculate -> return structured data."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from report_service.services.anomaly_detector import detect_zscore_anomalies
from report_service.services.health_index_calculator import (
    calculate_component_score,
    calculate_overall_score,
)
from shared.log_codes import REPORT_PROCESSING
from shared.observability import get_logger
from shared.schemas.report import ReportJobMessage

logger = get_logger(__name__)


async def generate_report_data(session: AsyncSession, job: ReportJobMessage) -> dict:
    logger.info(
        "Report generation started",
        code=REPORT_PROCESSING,
        report_id=str(job.report_id),
        report_type=job.report_type,
    )

    loco_id = UUID(job.locomotive_id) if job.locomotive_id else None
    start = job.date_range.start
    end = job.date_range.end

    locomotive_type = await _query_locomotive_type(session, loco_id)
    sensor_stats = await _query_sensor_stats(session, loco_id, start, end)
    health_trend = await _query_health_trend(session, loco_id, start, end)
    latest_health = await _query_latest_health(session, loco_id, start, end)
    alerts = await _query_alerts(session, loco_id, start, end)
    anomalies = await _detect_anomalies(session, loco_id, start, end)

    logger.info(
        "Report data collected",
        sensor_count=len(sensor_stats),
        trend_points=len(health_trend),
        alert_count=len(alerts),
        anomaly_sensors=len(anomalies),
    )

    # Calculate component health scores from average sensor values
    components = []
    for stat in sensor_stats:
        comp = calculate_component_score(stat["sensor_type"], stat["avg"], stat["unit"])
        components.append(comp)
    overall_score = calculate_overall_score(components) * 100  # scale to 0-100

    return {
        "locomotive_id": str(loco_id) if loco_id else None,
        "locomotive_type": locomotive_type,
        "report_type": job.report_type,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "health_overview": {
            "calculated_score": round(overall_score, 2),
            "avg_score": latest_health.get("avg_score", 0.0),
            "min_score": latest_health.get("min_score", 0.0),
            "max_score": latest_health.get("max_score", 0.0),
            "category": latest_health.get("category", "N/A"),
            "damage_penalty": latest_health.get("damage_penalty", 0.0),
            "top_factors": latest_health.get("top_factors", []),
            "trend": health_trend,
        },
        "sensor_stats": sensor_stats,
        "alerts": alerts,
        "alert_summary": _summarize_alerts(alerts),
        "anomalies": anomalies,
        "components": [c.model_dump() for c in components],
        "generated_at": datetime.now(UTC).isoformat(),
    }


async def _query_locomotive_type(session: AsyncSession, loco_id: UUID | None) -> str:
    if not loco_id:
        return "Парк"
    result = await session.execute(
        text("SELECT locomotive_type FROM raw_telemetry WHERE locomotive_id = :loco_id LIMIT 1"),
        {"loco_id": loco_id},
    )
    row = result.fetchone()
    return row.locomotive_type if row else "N/A"


async def _query_sensor_stats(
    session: AsyncSession, loco_id: UUID | None, start: datetime, end: datetime
) -> list[dict]:
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


async def _query_health_trend(
    session: AsyncSession, loco_id: UUID | None, start: datetime, end: datetime
) -> list[dict]:
    params: dict = {"start": start, "end": end}
    where_loco = ""
    if loco_id:
        where_loco = "AND locomotive_id = :loco_id"
        params["loco_id"] = loco_id

    result = await session.execute(
        text(f"""
            SELECT time_bucket('1 minute', calculated_at) AS bucket,
                   AVG(score) AS avg_score,
                   MIN(score) AS min_score,
                   MAX(score) AS max_score
            FROM health_snapshots
            WHERE calculated_at BETWEEN :start AND :end {where_loco}
            GROUP BY bucket
            ORDER BY bucket
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


async def _query_latest_health(session: AsyncSession, loco_id: UUID | None, start: datetime, end: datetime) -> dict:
    params: dict = {"start": start, "end": end}
    where_loco = ""
    if loco_id:
        where_loco = "AND locomotive_id = :loco_id"
        params["loco_id"] = loco_id

    agg_result = await session.execute(
        text(f"""
            SELECT AVG(score) AS avg_score,
                   MIN(score) AS min_score,
                   MAX(score) AS max_score
            FROM health_snapshots
            WHERE calculated_at BETWEEN :start AND :end {where_loco}
        """),
        params,
    )
    agg = agg_result.fetchone()

    latest_result = await session.execute(
        text(f"""
            SELECT score, category, top_factors, damage_penalty
            FROM health_snapshots
            WHERE calculated_at BETWEEN :start AND :end {where_loco}
            ORDER BY calculated_at DESC
            LIMIT 1
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


async def _query_alerts(session: AsyncSession, loco_id: UUID | None, start: datetime, end: datetime) -> list[dict]:
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


def _summarize_alerts(alerts: list[dict]) -> dict:
    summary: dict[str, int] = {}
    for alert in alerts:
        sev = alert["severity"]
        summary[sev] = summary.get(sev, 0) + 1
    return {"total": len(alerts), "by_severity": summary}


async def _detect_anomalies(
    session: AsyncSession, loco_id: UUID | None, start: datetime, end: datetime
) -> dict[str, list[dict]]:
    params: dict = {"start": start, "end": end}
    where_loco = ""
    if loco_id:
        where_loco = "AND locomotive_id = :loco_id"
        params["loco_id"] = loco_id

    result = await session.execute(
        text(f"""
            SELECT sensor_type, filtered_value, time
            FROM raw_telemetry
            WHERE time BETWEEN :start AND :end {where_loco}
            ORDER BY sensor_type, time
        """),
        params,
    )
    rows = result.fetchall()

    series: dict[str, list[tuple[float, str]]] = {}
    for row in rows:
        s = series.setdefault(row.sensor_type, [])
        s.append((float(row.filtered_value), row.time.isoformat()))

    anomalies: dict[str, list[dict]] = {}
    for sensor_type, values_times in series.items():
        values = [v for v, _t in values_times]
        indices = detect_zscore_anomalies(values, threshold=3.0)
        if indices:
            anomalies[sensor_type] = [
                {"index": i, "value": round(values_times[i][0], 4), "time": values_times[i][1]}
                for i in indices[:20]  # cap at 20 per sensor
            ]

    return anomalies
