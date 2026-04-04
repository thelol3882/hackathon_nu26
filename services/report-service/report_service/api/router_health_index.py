from fastapi import APIRouter

from report_service.api.dependencies import DbSession
from shared.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/{locomotive_id}")
async def get_health_index(locomotive_id: str, db: DbSession):
    """Get current health index for a locomotive."""
    logger.info("Health index requested", locomotive_id=locomotive_id)
    # TODO: implement
    return {"locomotive_id": locomotive_id, "overall_score": 0.0, "components": []}
