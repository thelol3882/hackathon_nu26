from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from report_service.api.dependencies import DbSession
from report_service.services.health_index_calculator import (
    calculate_component_score,
    calculate_overall_score,
)
from shared.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/{locomotive_id}")
async def get_health_index(locomotive_id: str, db: DbSession):
    """Get current health index for a locomotive based on latest data."""
    logger.info("Health index requested", locomotive_id=locomotive_id)

    snapshot_result = await db.execute(
        text("""
            SELECT score, category, top_factors, damage_penalty, calculated_at
            FROM health_snapshots
            WHERE locomotive_id = :loco_id
            ORDER BY calculated_at DESC
            LIMIT 1
        """),
        {"loco_id": locomotive_id},
    )
    snapshot = snapshot_result.fetchone()

    sensors_result = await db.execute(
        text("""
            SELECT DISTINCT ON (sensor_type) sensor_type, filtered_value, unit
            FROM raw_telemetry
            WHERE locomotive_id = :loco_id
            ORDER BY sensor_type, time DESC
        """),
        {"loco_id": locomotive_id},
    )
    sensors = sensors_result.fetchall()

    if not snapshot and not sensors:
        raise HTTPException(status_code=404, detail="No data found for locomotive")

    components = []
    for row in sensors:
        comp = calculate_component_score(row.sensor_type, float(row.filtered_value), row.unit)
        components.append(comp)

    overall_score = calculate_overall_score(components) * 100

    return {
        "locomotive_id": locomotive_id,
        "overall_score": round(overall_score, 2),
        "category": snapshot.category if snapshot else "N/A",
        "snapshot_score": round(float(snapshot.score), 2) if snapshot else None,
        "damage_penalty": round(float(snapshot.damage_penalty), 4) if snapshot else 0.0,
        "top_factors": snapshot.top_factors if snapshot else [],
        "calculated_at": snapshot.calculated_at.isoformat() if snapshot else None,
        "components": [c.model_dump() for c in components],
    }
