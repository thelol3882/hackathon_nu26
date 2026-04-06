from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api_gateway.api.dependencies import Analytics
from shared.schemas.alert import AlertEvent

router = APIRouter()


@router.get("/", response_model=list[AlertEvent])
async def list_alerts(
    analytics: Analytics,
    locomotive_id: str | None = Query(None),
    severity: str | None = Query(None),
    acknowledged: bool | None = Query(None),
    start: datetime | None = Query(None, description="Filter alerts from this time"),
    end: datetime | None = Query(None, description="Filter alerts until this time"),
    offset: int = 0,
    limit: int = 50,
):
    """List alerts with optional filters."""
    result = await analytics.list_alerts(
        locomotive_id=locomotive_id or "",
        severity=severity or "",
        acknowledged=acknowledged,
        start=start.isoformat() if start else "",
        end=end.isoformat() if end else "",
        offset=offset,
        limit=limit,
    )
    return [AlertEvent(**a) for a in result["alerts"]]


@router.get("/{alert_id}", response_model=AlertEvent)
async def get_alert(alert_id: str, analytics: Analytics):
    """Get a single alert by ID."""
    try:
        data = await analytics.get_alert(alert_id)
    except Exception as exc:
        if "NOT_FOUND" in str(exc):
            raise HTTPException(status_code=404, detail="Alert not found") from exc
        raise
    return AlertEvent(**data)


@router.post("/{alert_id}/acknowledge", response_model=AlertEvent)
async def acknowledge_alert(alert_id: str, analytics: Analytics):
    """Acknowledge an alert."""
    try:
        data = await analytics.acknowledge_alert(alert_id)
    except Exception as exc:
        if "NOT_FOUND" in str(exc):
            raise HTTPException(status_code=404, detail="Alert not found") from exc
        raise
    return AlertEvent(**data)
