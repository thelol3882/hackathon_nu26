from fastapi import APIRouter

from api_gateway.api.dependencies import DbSession

router = APIRouter()


@router.get("/")
async def list_alerts(db: DbSession, offset: int = 0, limit: int = 50):
    """List recent alerts."""
    # TODO: implement
    return []


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, db: DbSession):
    """Acknowledge an alert."""
    # TODO: implement
    return {"status": "acknowledged", "alert_id": alert_id}
