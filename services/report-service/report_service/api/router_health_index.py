from fastapi import APIRouter

from report_service.api.dependencies import DbPool

router = APIRouter()


@router.get("/{locomotive_id}")
async def get_health_index(locomotive_id: str, db: DbPool):
    """Get current health index for a locomotive."""
    # TODO: implement
    return {"locomotive_id": locomotive_id, "overall_score": 0.0, "components": []}
