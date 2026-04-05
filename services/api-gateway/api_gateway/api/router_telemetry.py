from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from starlette.responses import JSONResponse

from api_gateway.api.dependencies import Analytics

router = APIRouter()


class TelemetryBucket(BaseModel):
    bucket: str
    locomotive_id: str
    sensor_type: str
    avg_value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    last_value: float | None = None
    unit: str


@router.get("/", response_model=list[TelemetryBucket])
async def get_telemetry(
    analytics: Analytics,
    locomotive_id: str | None = Query(None),
    sensor_type: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    offset: int = 0,
    limit: int = 500,
):
    """Query historical telemetry. Resolution is selected automatically
    based on the requested time range."""
    result = await analytics.get_telemetry_bucketed(
        locomotive_id=locomotive_id or "",
        sensor_type=sensor_type or "",
        start=start.isoformat() if start else "",
        end=end.isoformat() if end else "",
        offset=offset,
        limit=limit,
    )
    return JSONResponse(
        content=result["points"],
        headers={"X-Data-Source": result["data_source"]},
    )


class TelemetrySnapshot(BaseModel):
    locomotive_id: str
    locomotive_type: str = ""
    sensor_type: str
    value: float
    filtered_value: float | None = None
    unit: str
    time: str
    latitude: float | None = None
    longitude: float | None = None


@router.get("/snapshot", response_model=list[TelemetrySnapshot])
async def get_telemetry_snapshot(
    analytics: Analytics,
    locomotive_id: str = Query(..., description="Locomotive UUID"),
    at: datetime = Query(..., description="Point in time (ISO 8601)"),
):
    """Get the latest sensor readings at or before the given timestamp."""
    return await analytics.get_telemetry_snapshot(locomotive_id, at.isoformat())


class TelemetryRaw(BaseModel):
    time: str
    locomotive_id: str
    locomotive_type: str = ""
    sensor_type: str
    value: float
    filtered_value: float | None = None
    unit: str
    latitude: float | None = None
    longitude: float | None = None


@router.get("/raw", response_model=list[TelemetryRaw])
async def get_telemetry_raw(
    analytics: Analytics,
    locomotive_id: str | None = Query(None),
    sensor_type: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    offset: int = 0,
    limit: int = 200,
):
    """Query raw telemetry data without aggregation."""
    return await analytics.get_telemetry_raw(
        locomotive_id=locomotive_id or "",
        sensor_type=sensor_type or "",
        start=start.isoformat() if start else "",
        end=end.isoformat() if end else "",
        offset=offset,
        limit=limit,
    )
