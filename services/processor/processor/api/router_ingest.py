from fastapi import APIRouter

from processor.api.dependencies import DbPool, Redis
from shared.schemas.telemetry import TelemetryReading

router = APIRouter()


@router.post("/ingest")
async def ingest_telemetry(
    reading: TelemetryReading,
    db: DbPool,
    redis: Redis,
):
    """Receive a telemetry reading, persist to TimescaleDB, publish to Redis."""
    # TODO: implement persistence and publishing
    return {"status": "accepted", "locomotive_id": str(reading.locomotive_id)}


@router.post("/ingest/batch")
async def ingest_batch(
    readings: list[TelemetryReading],
    db: DbPool,
    redis: Redis,
):
    """Receive a batch of telemetry readings."""
    # TODO: implement batch persistence
    return {"status": "accepted", "count": len(readings)}
