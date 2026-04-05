"""Orchestrates report generation: query Analytics Service via gRPC -> calculate -> return structured data."""

from __future__ import annotations

from datetime import UTC, datetime

from report_service.services.anomaly_detector import detect_zscore_anomalies
from report_service.services.health_index_calculator import (
    calculate_component_score,
    calculate_overall_score,
)
from shared.grpc_client import AnalyticsClient
from shared.log_codes import REPORT_PROCESSING
from shared.observability import get_logger
from shared.schemas.report import ReportJobMessage

logger = get_logger(__name__)


async def generate_report_data(analytics: AnalyticsClient, job: ReportJobMessage) -> dict:
    """Generate report data by querying Analytics Service via gRPC."""
    logger.info(
        "Report generation started",
        code=REPORT_PROCESSING,
        report_id=str(job.report_id),
        report_type=job.report_type,
    )

    loco_id = job.locomotive_id
    start = job.date_range.start.isoformat()
    end = job.date_range.end.isoformat()

    if loco_id is None:
        return await _generate_fleet_report(analytics, start, end, job)

    return await _generate_single_report(analytics, loco_id, start, end, job)


async def _generate_single_report(
    analytics: AnalyticsClient,
    loco_id: str,
    start: str,
    end: str,
    job: ReportJobMessage,
) -> dict:
    stats_data = await analytics.get_sensor_stats(locomotive_id=loco_id, start=start, end=end)
    sensor_stats = stats_data["stats"]
    locomotive_type = stats_data["locomotive_type"]
    health_trend = await analytics.get_health_trend(locomotive_id=loco_id, start=start, end=end)
    latest_health = await analytics.get_latest_health(locomotive_id=loco_id, start=start, end=end)
    alerts = await analytics.get_report_alerts(locomotive_id=loco_id, start=start, end=end)
    anomalies = await _detect_anomalies(analytics, loco_id, start, end)

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
        "locomotive_id": loco_id,
        "locomotive_type": locomotive_type,
        "report_type": job.report_type,
        "date_range": {"start": start, "end": end},
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
    analytics: AnalyticsClient,
    start: str,
    end: str,
    job: ReportJobMessage,
) -> dict:
    logger.info("Generating fleet report (aggregated)")

    fleet_health_list = await analytics.get_fleet_health(start=start, end=end)
    fleet_health = (
        fleet_health_list[0]
        if fleet_health_list
        else {
            "avg_score": 0,
            "min_score": 0,
            "max_score": 0,
            "locomotive_count": 0,
            "healthy_count": 0,
            "warning_count": 0,
            "critical_count": 0,
        }
    )
    fleet_alerts = await analytics.get_fleet_alert_summary(start=start, end=end)
    stats_data = await analytics.get_sensor_stats(start=start, end=end)
    fleet_sensor_stats = stats_data["stats"]
    worst_locos = await analytics.get_worst_locomotives(start=start, end=end)

    total_locos = fleet_health.get("locomotive_count", 0)
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
        "date_range": {"start": start, "end": end},
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
        "alerts": [],
        "alert_summary": fleet_alerts,
        "anomalies": {},
        "components": [],
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _summarize_alerts(alerts: list[dict]) -> dict:
    summary: dict[str, int] = {}
    for alert in alerts:
        sev = alert["severity"]
        summary[sev] = summary.get(sev, 0) + 1
    return {"total": len(alerts), "by_severity": summary}


async def _detect_anomalies(
    analytics: AnalyticsClient,
    loco_id: str,
    start: str,
    end: str,
) -> dict[str, list[dict]]:
    rows = await analytics.get_raw_for_anomalies(locomotive_id=loco_id, start=start, end=end)

    series: dict[str, list[tuple[float, str]]] = {}
    for row in rows:
        s = series.setdefault(row["sensor_type"], [])
        time_str = row["time"] if isinstance(row["time"], str) else row["time"].isoformat()
        s.append((row["filtered_value"], time_str))

    anomalies: dict[str, list[dict]] = {}
    for sensor_type, values_times in series.items():
        values = [v for v, _t in values_times]
        indices = detect_zscore_anomalies(values, threshold=3.0)
        if indices:
            anomalies[sensor_type] = [
                {"index": i, "value": round(values_times[i][0], 4), "time": values_times[i][1]} for i in indices[:20]
            ]

    return anomalies
