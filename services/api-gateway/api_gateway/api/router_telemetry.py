from datetime import datetime

from fastapi import APIRouter, Query

from api_gateway.api.dependencies import DbPool

router = APIRouter()


@router.get("/")
async def get_telemetry(
    db: DbPool,
    locomotive_id: str | None = Query(None),
    sensor_type: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    offset: int = 0,
    limit: int = 50,
):
    """Query historical telemetry data."""
    # TODO: implement with TimescaleDB time_bucket
    return []
