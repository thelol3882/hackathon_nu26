from fastapi import APIRouter, Query

from report_service.api.dependencies import Analytics
from shared.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/fleet")
async def fleet_analytics(analytics: Analytics):
    """Fleet-wide analytics: health distribution, counts by category."""
    logger.info("Fleet analytics requested")

    rows = await analytics.get_fleet_latest_snapshots()

    total = len(rows)
    by_category: dict[str, int] = {}
    by_type: dict[str, int] = {}
    score_sum = 0.0

    for row in rows:
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
        by_type[row["locomotive_type"]] = by_type.get(row["locomotive_type"], 0) + 1
        score_sum += row["score"]

    return {
        "total_locomotives": total,
        "avg_health_score": round(score_sum / total, 2) if total else 0.0,
        "by_category": by_category,
        "by_type": by_type,
    }


@router.get("/utilization")
async def utilization(
    analytics: Analytics,
    locomotive_id: str | None = Query(None),
    hours: int = Query(24, ge=1, le=168),
):
    """Utilization statistics based on speed > 0 readings."""
    logger.info("Utilization stats requested", locomotive_id=locomotive_id)

    stats = await analytics.get_utilization(locomotive_id=locomotive_id or "", hours=hours)

    total = stats["total_readings"]
    active = stats["active_readings"]

    return {
        "period_hours": hours,
        "locomotive_id": locomotive_id,
        "total_readings": total,
        "active_readings": active,
        "utilization_rate": round(active / total, 4) if total else 0.0,
        "avg_speed_kmh": stats["avg_speed"],
        "max_speed_kmh": stats["max_speed"],
    }
