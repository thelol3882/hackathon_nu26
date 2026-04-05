from datetime import datetime

from fastapi import APIRouter, Query
from starlette.responses import JSONResponse

from api_gateway.api.dependencies import TsSession
from api_gateway.services.telemetry_service import (
    TelemetryBucket,
    TelemetryRaw,
    TelemetrySnapshot,
    query_telemetry_bucketed,
    query_telemetry_raw,
    query_telemetry_snapshot,
)

router = APIRouter()


@router.get("/", response_model=list[TelemetryBucket])
async def get_telemetry(
    db: TsSession,
    locomotive_id: str | None = Query(None),
    sensor_type: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    offset: int = 0,
    limit: int = 500,
):
    """Query historical telemetry. Resolution is selected automatically
    based on the requested time range."""
    buckets, data_source = await query_telemetry_bucketed(
        db,
        locomotive_id=locomotive_id,
        sensor_type=sensor_type,
        start=start,
        end=end,
        offset=offset,
        limit=limit,
    )
    return JSONResponse(
        content=[b.model_dump(mode="json") for b in buckets],
        headers={"X-Data-Source": data_source},
    )


@router.get("/snapshot", response_model=list[TelemetrySnapshot])
async def get_telemetry_snapshot(
    db: TsSession,
    locomotive_id: str = Query(..., description="Locomotive UUID"),
    at: datetime = Query(..., description="Point in time (ISO 8601)"),
):
    """Get the latest sensor readings at or before the given timestamp."""
    return await query_telemetry_snapshot(db, locomotive_id=locomotive_id, at=at)


@router.get("/raw", response_model=list[TelemetryRaw])
async def get_telemetry_raw(
    db: TsSession,
    locomotive_id: str | None = Query(None),
    sensor_type: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    offset: int = 0,
    limit: int = 200,
):
    """Query raw telemetry data without aggregation."""
    return await query_telemetry_raw(
        db,
        locomotive_id=locomotive_id,
        sensor_type=sensor_type,
        start=start,
        end=end,
        offset=offset,
        limit=limit,
    )
