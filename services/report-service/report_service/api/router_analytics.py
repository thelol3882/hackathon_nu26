from fastapi import APIRouter

from report_service.api.dependencies import DbSession
from shared.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/fleet")
async def fleet_analytics(db: DbSession):
    """Fleet-wide analytics summary."""
    logger.info("Fleet analytics requested")
    # TODO: implement
    return {}


@router.get("/utilization")
async def utilization(db: DbSession, locomotive_id: str | None = None):
    """Utilization statistics."""
    logger.info("Utilization stats requested", locomotive_id=locomotive_id)
    # TODO: implement
    return {}
