from datetime import datetime

from fastapi import APIRouter, Query

from api_gateway.api.dependencies import DbSession
from api_gateway.services import alert_service
from shared.schemas.alert import AlertEvent

router = APIRouter()


@router.get("/", response_model=list[AlertEvent])
async def list_alerts(
    db: DbSession,
    locomotive_id: str | None = Query(None),
    severity: str | None = Query(None),
    acknowledged: bool | None = Query(None),
    start: datetime | None = Query(None, description="Filter alerts from this time"),
    end: datetime | None = Query(None, description="Filter alerts until this time"),
    offset: int = 0,
    limit: int = 50,
):
    """List alerts with optional filters."""
    return await alert_service.list_alerts(
        db,
        locomotive_id=locomotive_id,
        severity=severity,
        acknowledged=acknowledged,
        start=start,
        end=end,
        offset=offset,
        limit=limit,
    )


@router.get("/{alert_id}", response_model=AlertEvent)
async def get_alert(alert_id: str, db: DbSession):
    """Get a single alert by ID."""
    return await alert_service.get_alert(db, alert_id)


@router.post("/{alert_id}/acknowledge", response_model=AlertEvent)
async def acknowledge_alert(alert_id: str, db: DbSession):
    """Acknowledge an alert."""
    return await alert_service.acknowledge_alert(db, alert_id)
