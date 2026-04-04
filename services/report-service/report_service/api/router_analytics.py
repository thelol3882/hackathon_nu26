from fastapi import APIRouter

from report_service.api.dependencies import DbPool

router = APIRouter()


@router.get("/fleet")
async def fleet_analytics(db: DbPool):
    """Fleet-wide analytics summary."""
    # TODO: implement
    return {}


@router.get("/utilization")
async def utilization(db: DbPool, locomotive_id: str | None = None):
    """Utilization statistics."""
    # TODO: implement
    return {}
