from fastapi import APIRouter

from report_service.api.dependencies import DbSession

router = APIRouter()


@router.get("/fleet")
async def fleet_analytics(db: DbSession):
    """Fleet-wide analytics summary."""
    # TODO: implement
    return {}


@router.get("/utilization")
async def utilization(db: DbSession, locomotive_id: str | None = None):
    """Utilization statistics."""
    # TODO: implement
    return {}
