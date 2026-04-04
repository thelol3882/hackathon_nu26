"""Fleet-wide aggregation and utilization statistics."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.observability import get_logger

logger = get_logger(__name__)


async def get_fleet_summary(session: AsyncSession) -> dict:
    """Aggregate fleet-wide statistics from health snapshots."""
    logger.info("Fetching fleet summary")

    result = await session.execute(
        text("""
            SELECT locomotive_id, locomotive_type, score, category
            FROM (
                SELECT locomotive_id, locomotive_type, score, category,
                       ROW_NUMBER() OVER (PARTITION BY locomotive_id ORDER BY calculated_at DESC) AS rn
                FROM health_snapshots
            ) sub
            WHERE rn = 1
        """)
    )
    rows = result.fetchall()

    total = len(rows)
    categories: dict[str, int] = {}
    score_sum = 0.0

    for row in rows:
        categories[row.category] = categories.get(row.category, 0) + 1
        score_sum += float(row.score)

    return {
        "total_locomotives": total,
        "by_category": categories,
        "avg_health_score": round(score_sum / total, 2) if total else 0.0,
    }


async def get_utilization_stats(session: AsyncSession, locomotive_id: str | None = None) -> dict:
    """Calculate utilization rates from speed readings."""
    logger.info("Calculating utilization stats", locomotive_id=locomotive_id)

    params: dict = {}
    where_loco = ""
    if locomotive_id:
        where_loco = "AND locomotive_id = :loco_id"
        params["loco_id"] = locomotive_id

    result = await session.execute(
        text(f"""
            SELECT
                COUNT(*) AS total_readings,
                COUNT(*) FILTER (WHERE filtered_value > 0) AS active_readings,
                AVG(filtered_value) AS avg_speed
            FROM raw_telemetry
            WHERE sensor_type = 'speed_actual'
              AND time >= NOW() - INTERVAL '24 hours'
              {where_loco}
        """),
        params,
    )
    row = result.fetchone()

    total = int(row.total_readings) if row and row.total_readings else 0
    active = int(row.active_readings) if row and row.active_readings else 0

    return {
        "utilization_rate": round(active / total, 4) if total else 0.0,
        "avg_speed_kmh": round(float(row.avg_speed), 2) if row and row.avg_speed else 0.0,
        "total_readings": total,
    }
