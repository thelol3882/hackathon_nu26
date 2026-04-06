from fastapi import APIRouter, HTTPException

from report_service.api.dependencies import Analytics
from shared.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/{locomotive_id}")
async def get_health_index(locomotive_id: str, analytics: Analytics):
    """Get current health index for a locomotive via Analytics Service."""
    logger.info("Health index requested", locomotive_id=locomotive_id)

    try:
        data = await analytics.get_current_health(locomotive_id)
    except Exception as exc:
        if "NOT_FOUND" in str(exc):
            raise HTTPException(status_code=404, detail="No data found for locomotive") from exc
        raise

    return {
        "locomotive_id": locomotive_id,
        "overall_score": data["overall_score"],
        "category": data["category"],
        "top_factors": data.get("top_factors", []),
        "damage_penalty": data.get("damage_penalty", 0.0),
        "calculated_at": data.get("calculated_at"),
    }
