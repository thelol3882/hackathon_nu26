from datetime import datetime

from fastapi import APIRouter, Query

from api_gateway.api.dependencies import DbSession
from api_gateway.services.telemetry_query_service import (
    TelemetryBucket,
    TelemetryRaw,
    query_telemetry_bucketed,
    query_telemetry_raw,
)

router = APIRouter()


@router.get("/", response_model=list[TelemetryBucket])
async def get_telemetry(
    db: DbSession,
    locomotive_id: str | None = Query(None),
    sensor_type: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    bucket_interval: str = Query(
        "1 minute",
        description="Aggregation interval: 1 minute, 5 minutes, 15 minutes, 1 hour, 1 day",
    ),
    offset: int = 0,
    limit: int = 50,
):
    """Query historical telemetry data with time-bucket aggregation."""
    return await query_telemetry_bucketed(
        db,
        locomotive_id=locomotive_id,
        sensor_type=sensor_type,
        start=start,
        end=end,
        bucket_interval=bucket_interval,
        offset=offset,
        limit=limit,
    )


@router.get("/raw", response_model=list[TelemetryRaw])
async def get_telemetry_raw(
    db: DbSession,
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
