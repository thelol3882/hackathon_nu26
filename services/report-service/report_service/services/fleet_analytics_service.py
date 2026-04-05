"""Fleet-wide aggregation and utilization statistics."""

from sqlalchemy.ext.asyncio import AsyncSession

from report_service.repositories import health_snapshot_repository, telemetry_repository
from shared.observability import get_logger

logger = get_logger(__name__)


async def get_fleet_summary(session: AsyncSession) -> dict:
    """Aggregate fleet-wide statistics from health snapshots."""
    logger.info("Fetching fleet summary")

    rows = await health_snapshot_repository.query_fleet_latest_snapshots(session)

    total = len(rows)
    categories: dict[str, int] = {}
    score_sum = 0.0

    for row in rows:
        categories[row["category"]] = categories.get(row["category"], 0) + 1
        score_sum += row["score"]

    return {
        "total_locomotives": total,
        "by_category": categories,
        "avg_health_score": round(score_sum / total, 2) if total else 0.0,
    }


async def get_utilization_stats(session: AsyncSession, locomotive_id: str | None = None) -> dict:
    """Calculate utilization rates from speed readings."""
    logger.info("Calculating utilization stats", locomotive_id=locomotive_id)
    raw = await telemetry_repository.query_utilization(session, locomotive_id, hours=24)
    total = raw["total_readings"]
    active = raw["active_readings"]
    return {
        "utilization_rate": round(active / total, 4) if total else 0.0,
        "avg_speed_kmh": raw["avg_speed"],
        "total_readings": total,
    }
