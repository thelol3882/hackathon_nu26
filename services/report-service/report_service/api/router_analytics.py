from fastapi import APIRouter, Query
from sqlalchemy import text

from report_service.api.dependencies import DbSession
from shared.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/fleet")
async def fleet_analytics(db: DbSession):
    """Fleet-wide analytics: health distribution, counts by category."""
    logger.info("Fleet analytics requested")

    # Latest health snapshot per locomotive
    result = await db.execute(
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
    by_category: dict[str, int] = {}
    by_type: dict[str, int] = {}
    score_sum = 0.0

    for row in rows:
        by_category[row.category] = by_category.get(row.category, 0) + 1
        by_type[row.locomotive_type] = by_type.get(row.locomotive_type, 0) + 1
        score_sum += float(row.score)

    return {
        "total_locomotives": total,
        "avg_health_score": round(score_sum / total, 2) if total else 0.0,
        "by_category": by_category,
        "by_type": by_type,
    }


@router.get("/utilization")
async def utilization(
    db: DbSession,
    locomotive_id: str | None = Query(None),
    hours: int = Query(24, ge=1, le=168),
):
    """Utilization statistics based on speed > 0 readings."""
    logger.info("Utilization stats requested", locomotive_id=locomotive_id)

    params: dict = {"hours": hours}
    where_loco = ""
    if locomotive_id:
        where_loco = "AND locomotive_id = :loco_id"
        params["loco_id"] = locomotive_id

    result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) AS total_readings,
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
        "period_hours": hours,
        "locomotive_id": locomotive_id,
        "total_readings": total,
        "active_readings": active,
        "utilization_rate": round(active / total, 4) if total else 0.0,
        "avg_speed_kmh": round(float(row.avg_speed), 2) if row and row.avg_speed else 0.0,
        "max_speed_kmh": round(float(row.max_speed), 2) if row and row.max_speed else 0.0,
    }
