"""
Telemetry ingest endpoints.

Pipeline per reading:
  1. EMA filter + flatten → TelemetryRecord ORM rows
  2. Bulk INSERT raw_telemetry
  3. Evaluate alerts → INSERT alert_events + publish alerts:live
  4. Calculate HealthIndex → INSERT health_snapshots + publish health:live
  5. Publish full reading to telemetry:live
"""

import asyncio

from fastapi import APIRouter
from sqlalchemy.dialects.postgresql import insert as pg_insert

from processor.api.dependencies import DbSession, Redis
from processor.core.redis_client import publish_alert, publish_health, publish_telemetry
from processor.models.alert_entity import AlertRecord
from processor.models.health_entity import HealthSnapshotRecord
from processor.models.telemetry_entity import TelemetryRecord
from processor.services.alert_evaluator import evaluate_alerts
from processor.services.health_service import calculate_health
from processor.services.ingestion_service import flatten_reading
from shared.observability import get_logger
from shared.observability.prometheus import (
    alerts_fired_total,
    health_index_calculated_total,
    health_index_value,
    telemetry_ingested_total,
)
from shared.schemas.telemetry import TelemetryReading
from shared.utils import generate_id
from shared.wire import encode as wire_encode

logger = get_logger(__name__)

router = APIRouter()


async def _process_single(
    reading: TelemetryReading,
    db: DbSession,
) -> dict:
    """
    Run the full ingest pipeline for one TelemetryReading.
    Returns a summary dict for the response body.
    """
    loco_id = str(reading.locomotive_id)

    # flatten_reading mutates sensor.value → filtered; returns DB rows
    rows = flatten_reading(reading)

    if rows:
        stmt = (
            pg_insert(TelemetryRecord)
            .values(
                [
                    {
                        "time": r.time,
                        "locomotive_id": r.locomotive_id,
                        "locomotive_type": r.locomotive_type,
                        "sensor_type": r.sensor_type,
                        "value": r.value,
                        "filtered_value": r.filtered_value,
                        "unit": r.unit,
                        "sample_rate_hz": r.sample_rate_hz,
                        "latitude": r.latitude,
                        "longitude": r.longitude,
                    }
                    for r in rows
                ]
            )
            .on_conflict_do_nothing()
        )
        await db.execute(stmt)

    # Uses already-filtered sensor.value (mutated by flatten_reading above)
    alert_events = evaluate_alerts(reading)

    alert_records = [
        AlertRecord(
            id=ae.id,
            locomotive_id=ae.locomotive_id,
            locomotive_type=reading.locomotive_type.value,
            sensor_type=str(ae.sensor_type),
            severity=ae.severity.value,
            value=ae.value,
            threshold_min=ae.threshold_min,
            threshold_max=ae.threshold_max,
            message=ae.message,
            timestamp=ae.timestamp,
            acknowledged=ae.acknowledged,
        )
        for ae in alert_events
    ]
    if alert_records:
        db.add_all(alert_records)

    health = calculate_health(reading)

    health_record = HealthSnapshotRecord(
        id=generate_id(),
        locomotive_id=reading.locomotive_id,
        locomotive_type=reading.locomotive_type.value,
        score=health.overall_score,
        category=health.category,
        top_factors=[f.model_dump() for f in health.top_factors],
        damage_penalty=health.damage_penalty,
        calculated_at=health.calculated_at,
    )
    db.add(health_record)

    await db.commit()

    telemetry_ingested_total.labels(locomotive_type=reading.locomotive_type.value).inc(len(reading.sensors))
    health_index_calculated_total.inc()
    health_index_value.labels(locomotive_id=loco_id, locomotive_type=reading.locomotive_type.value).set(
        health.overall_score
    )
    for ae in alert_events:
        alerts_fired_total.labels(severity=ae.severity.value, sensor_type=str(ae.sensor_type)).inc()

    # Publish to Redis fire-and-forget (non-blocking)
    telemetry_payload = wire_encode(reading.model_dump(mode="json"))
    health_payload = wire_encode(health.model_dump(mode="json"))
    alert_payloads = [wire_encode(ae.model_dump(mode="json")) for ae in alert_events]

    publish_tasks = [
        publish_telemetry(loco_id, telemetry_payload),
        publish_health(loco_id, health_payload),
    ]
    publish_tasks += [publish_alert(ap) for ap in alert_payloads]
    await asyncio.gather(*publish_tasks, return_exceptions=True)

    return {
        "locomotive_id": loco_id,
        "rows_written": len(rows),
        "alerts_raised": len(alert_events),
        "health_score": health.overall_score,
        "health_category": health.category,
    }


@router.post("/ingest")
async def ingest_telemetry(
    reading: TelemetryReading,
    db: DbSession,
    redis: Redis,
):
    logger.info(
        "Ingest request received",
        locomotive_id=str(reading.locomotive_id),
        sensor_count=len(reading.sensors),
    )
    result = await _process_single(reading, db)
    return {"status": "accepted", **result}


@router.post("/ingest/batch")
async def ingest_batch(
    readings: list[TelemetryReading],
    db: DbSession,
    redis: Redis,
):
    """
    Receive a batch of TelemetryReadings.
    Each reading is processed independently; partial failures are captured
    and reported without aborting the whole batch.
    """
    logger.info("Batch ingest request received", batch_size=len(readings))
    results = []
    errors: list[dict] = []

    for reading in readings:
        try:
            r = await _process_single(reading, db)
            results.append(r)
        except Exception as exc:
            logger.error(
                "Batch item processing failed",
                locomotive_id=str(reading.locomotive_id),
                error=str(exc),
            )
            errors.append(
                {
                    "locomotive_id": str(reading.locomotive_id),
                    "error": str(exc),
                }
            )

    logger.info(
        "Batch ingest completed",
        processed=len(results),
        failed=len(errors),
    )
    return {
        "status": "accepted",
        "processed": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }
