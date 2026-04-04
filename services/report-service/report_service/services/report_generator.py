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
    """Generate report data by querying telemetry, health, and alert tables."""
    logger.info(
        "Report generation started",
        code=REPORT_PROCESSING,
        report_id=str(job.report_id),
        report_type=job.report_type,
    )

    loco_id = UUID(job.locomotive_id) if job.locomotive_id else None
    start = job.date_range.start
    end = job.date_range.end

    # Fleet-wide report (no specific locomotive) uses aggregated queries
    if loco_id is None:
        return await _generate_fleet_report(session, start, end, job)

    return await _generate_single_report(session, loco_id, start, end, job)


async def _generate_single_report(
    session: AsyncSession, loco_id: UUID, start: datetime, end: datetime, job: ReportJobMessage
) -> dict:
    """Generate report for a single locomotive."""
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

    components = []
    for stat in sensor_stats:
        comp = calculate_component_score(stat["sensor_type"], stat["avg"], stat["unit"])
        components.append(comp)
    overall_score = calculate_overall_score(components) * 100

    return {
        "locomotive_id": str(loco_id),
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


async def _generate_fleet_report(
    session: AsyncSession, start: datetime, end: datetime, job: ReportJobMessage
) -> dict:
    """Generate aggregated fleet-wide report without loading all raw data."""
    logger.info("Generating fleet report (aggregated)")

    # Fleet health overview: aggregate health_snapshots per locomotive
    fleet_health = await _query_fleet_health(session, start, end)
    # Fleet alerts summary (aggregated, not individual rows)
    fleet_alerts = await _query_fleet_alert_summary(session, start, end)
    # Fleet sensor stats (aggregated across all locomotives)
    fleet_sensor_stats = await _query_sensor_stats(session, None, start, end)
    # Top unhealthy locomotives
    worst_locos = await _query_worst_locomotives(session, start, end)

    total_locos = fleet_health.get("total_locomotives", 0)
    avg_score = fleet_health.get("avg_score", 0.0)

    if avg_score >= 80:
        category = "Норма"
    elif avg_score >= 50:
        category = "Внимание"
    else:
        category = "Критично"

    return {
        "locomotive_id": None,
        "locomotive_type": "Парк",
        "report_type": "fleet",
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "health_overview": {
            "calculated_score": round(avg_score, 2),
            "avg_score": round(avg_score, 2),
            "min_score": fleet_health.get("min_score", 0.0),
            "max_score": fleet_health.get("max_score", 0.0),
            "category": category,
            "damage_penalty": 0.0,
            "top_factors": [],
            "trend": [],
            "fleet_stats": {
                "total_locomotives": total_locos,
                "healthy_count": fleet_health.get("healthy_count", 0),
                "warning_count": fleet_health.get("warning_count", 0),
                "critical_count": fleet_health.get("critical_count", 0),
            },
            "worst_locomotives": worst_locos,
        },
        "sensor_stats": fleet_sensor_stats,
        "alerts": [],  # Don't include individual alerts for fleet
        "alert_summary": fleet_alerts,
        "anomalies": {},  # Skip per-row anomaly detection for fleet
        "components": [],
        "generated_at": datetime.now(UTC).isoformat(),
    }


async def _query_fleet_health(session: AsyncSession, start: datetime, end: datetime) -> dict:
    """Aggregate health scores across all locomotives."""
    result = await session.execute(
        text("""
            WITH loco_scores AS (
                SELECT locomotive_id,
                       AVG(score) AS avg_score
                FROM health_snapshots
                WHERE calculated_at BETWEEN :start AND :end
                GROUP BY locomotive_id
            )
            SELECT
                COUNT(*) AS total_locomotives,
                AVG(avg_score) AS fleet_avg,
                MIN(avg_score) AS fleet_min,
                MAX(avg_score) AS fleet_max,
                COUNT(*) FILTER (WHERE avg_score >= 80) AS healthy_count,
                COUNT(*) FILTER (WHERE avg_score >= 50 AND avg_score < 80) AS warning_count,
                COUNT(*) FILTER (WHERE avg_score < 50) AS critical_count
            FROM loco_scores
        """),
        {"start": start, "end": end},
    )
    row = result.fetchone()
    if not row or not row.total_locomotives:
        return {"total_locomotives": 0, "avg_score": 0, "min_score": 0, "max_score": 0,
                "healthy_count": 0, "warning_count": 0, "critical_count": 0}
    return {
        "total_locomotives": int(row.total_locomotives),
        "avg_score": round(float(row.fleet_avg), 2),
        "min_score": round(float(row.fleet_min), 2),
        "max_score": round(float(row.fleet_max), 2),
        "healthy_count": int(row.healthy_count),
        "warning_count": int(row.warning_count),
        "critical_count": int(row.critical_count),
    }


async def _query_worst_locomotives(session: AsyncSession, start: datetime, end: datetime) -> list[dict]:
    """Get top 10 worst-performing locomotives."""
    result = await session.execute(
        text("""
            SELECT locomotive_id, locomotive_type,
                   AVG(score) AS avg_score,
                   MIN(score) AS min_score,
                   MAX(score) AS max_score,
                   COUNT(*) AS snapshot_count
            FROM health_snapshots
            WHERE calculated_at BETWEEN :start AND :end
            GROUP BY locomotive_id, locomotive_type
            ORDER BY AVG(score) ASC
            LIMIT 10
        """),
        {"start": start, "end": end},
    )
    return [
        {
            "locomotive_id": str(row.locomotive_id),
            "locomotive_type": row.locomotive_type,
            "avg_score": round(float(row.avg_score), 2),
            "min_score": round(float(row.min_score), 2),
            "max_score": round(float(row.max_score), 2),
        }
        for row in result.fetchall()
    ]


async def _query_fleet_alert_summary(session: AsyncSession, start: datetime, end: datetime) -> dict:
    """Get aggregated alert counts for the entire fleet."""
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


# ── Single locomotive queries ────────────────────────────────────────────────


async def _query_locomotive_type(session: AsyncSession, loco_id: UUID | None) -> str:
    """Get locomotive type from the most recent telemetry record."""
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
    """Aggregate sensor statistics from raw_telemetry."""
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
    """Get health score trend using time_bucket."""
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
    """Get the latest health snapshot and aggregate scores in the range."""
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
    """Get alert events in the date range."""
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
    """Count alerts by severity."""
    summary: dict[str, int] = {}
    for alert in alerts:
        sev = alert["severity"]
        summary[sev] = summary.get(sev, 0) + 1
    return {"total": len(alerts), "by_severity": summary}


async def _detect_anomalies(
    session: AsyncSession, loco_id: UUID | None, start: datetime, end: datetime
) -> dict[str, list[dict]]:
    """Run z-score anomaly detection per sensor for a single locomotive."""
    if not loco_id:
        return {}  # Skip for fleet — too expensive

    params: dict = {"start": start, "end": end, "loco_id": loco_id}

    result = await session.execute(
        text("""
            SELECT sensor_type, filtered_value, time
            FROM raw_telemetry
            WHERE time BETWEEN :start AND :end AND locomotive_id = :loco_id
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
                for i in indices[:20]
            ]

    return anomalies
