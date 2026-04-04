"""
Telemetry ingest endpoints.

POST /telemetry/ingest        — single TelemetryReading
POST /telemetry/ingest/batch  — list of TelemetryReading (bulk)

Pipeline per reading:
  1. EMA filter + flatten → TelemetryRecord ORM rows
  2. Bulk INSERT raw_telemetry
  3. Evaluate alerts → INSERT alert_events + publish alerts:live
  4. Calculate HealthIndex → INSERT health_snapshots + publish health:live
  5. Publish full reading to telemetry:live (for frontend WebSocket)
"""

import asyncio

from fastapi import APIRouter, Request
from sqlalchemy.dialects.postgresql import insert as pg_insert

from processor.api.dependencies import DbSession, Redis
from processor.core.redis_client import get_redis_raw, publish_alert, publish_health, publish_telemetry
from processor.models.alert_entity import AlertRecord
from processor.models.health_entity import HealthSnapshotRecord
from processor.models.telemetry_entity import TelemetryRecord
from processor.services.alert_evaluator import evaluate_alerts
from processor.services.db_writer import DbWriter
from processor.services.health_service import calculate_health
from processor.services.ingestion_service import flatten_reading
from shared.constants import ALERT_CHANNEL, HEALTH_CHANNEL, TELEMETRY_CHANNEL
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

    # ── 1. EMA filter + flatten ──────────────────────────────────────────
    # flatten_reading mutates sensor.value → filtered; returns DB rows
    rows = flatten_reading(reading)

    # ── 2. Bulk INSERT raw telemetry (skip duplicates) ────────────────
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

    # ── 3. Alert evaluation ─────────────────────────────────────────────
    # Uses already-filtered sensor.value (mutated by flatten_reading)
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

    # ── 4. Health Index calculation ─────────────────────────────────────
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

    # ── 5. Commit everything in one transaction ─────────────────────────
    await db.commit()

    # ── 6. Prometheus metrics ─────────────────────────────────────────────
    telemetry_ingested_total.labels(locomotive_type=reading.locomotive_type.value).inc(len(reading.sensors))
    health_index_calculated_total.inc()
    health_index_value.labels(locomotive_id=loco_id, locomotive_type=reading.locomotive_type.value).set(
        health.overall_score
    )
    for ae in alert_events:
        alerts_fired_total.labels(severity=ae.severity.value, sensor_type=str(ae.sensor_type)).inc()

    # ── 7. Publish to Redis async (fire-and-forget, non-blocking) ───────
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
    """Receive a single TelemetryReading and run the full processing pipeline."""
    logger.info(
        "Ingest request received",
        locomotive_id=str(reading.locomotive_id),
        sensor_count=len(reading.sensors),
    )
    result = await _process_single(reading, db)
    return {"status": "accepted", **result}


def _process_readings_sync(
    readings: list[TelemetryReading],
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[tuple[str, bytes]], list[dict]]:
    """CPU-bound processing — runs in a thread via run_in_executor.

    Returns plain dicts (not ORM objects) for thread-safe handoff to DbWriter.
    """
    results: list[dict] = []
    errors: list[dict] = []
    all_telemetry_rows: list[dict] = []
    all_alert_records: list[dict] = []
    all_health_records: list[dict] = []
    publish_items: list[tuple[str, bytes]] = []

    for reading in readings:
        loco_id = str(reading.locomotive_id)
        try:
            # ── 1. EMA filter + flatten ──
            rows = flatten_reading(reading)

            all_telemetry_rows.extend(
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
            )

            # ── 2. Alert evaluation ──
            alert_events = evaluate_alerts(reading)
            all_alert_records.extend(
                {
                    "id": ae.id,
                    "locomotive_id": ae.locomotive_id,
                    "locomotive_type": reading.locomotive_type.value,
                    "sensor_type": str(ae.sensor_type),
                    "severity": ae.severity.value,
                    "value": ae.value,
                    "threshold_min": ae.threshold_min,
                    "threshold_max": ae.threshold_max,
                    "message": ae.message,
                    "timestamp": ae.timestamp,
                    "acknowledged": ae.acknowledged,
                }
                for ae in alert_events
            )

            # ── 3. Health Index calculation ──
            health = calculate_health(reading)
            all_health_records.append(
                {
                    "id": generate_id(),
                    "locomotive_id": reading.locomotive_id,
                    "locomotive_type": reading.locomotive_type.value,
                    "score": health.overall_score,
                    "category": health.category,
                    "top_factors": [f.model_dump() for f in health.top_factors],
                    "damage_penalty": health.damage_penalty,
                    "calculated_at": health.calculated_at,
                }
            )

            # ── 4. Prometheus metrics ──
            telemetry_ingested_total.labels(locomotive_type=reading.locomotive_type.value).inc(len(reading.sensors))
            health_index_calculated_total.inc()
            health_index_value.labels(locomotive_id=loco_id, locomotive_type=reading.locomotive_type.value).set(
                health.overall_score
            )
            for ae in alert_events:
                alerts_fired_total.labels(severity=ae.severity.value, sensor_type=str(ae.sensor_type)).inc()

            # ── 5. Collect Redis publish items (channel, payload) ──
            reading_json = reading.model_dump(mode="json")
            health_json = health.model_dump(mode="json")
            publish_items.append((f"{TELEMETRY_CHANNEL}:{loco_id}", wire_encode(reading_json)))
            publish_items.append((f"{HEALTH_CHANNEL}:{loco_id}", wire_encode(health_json)))
            publish_items.extend((ALERT_CHANNEL, wire_encode(ae.model_dump(mode="json"))) for ae in alert_events)

            results.append(
                {
                    "locomotive_id": loco_id,
                    "rows_written": len(rows),
                    "alerts_raised": len(alert_events),
                    "health_score": health.overall_score,
                    "health_category": health.category,
                }
            )
        except Exception as exc:
            errors.append({"locomotive_id": loco_id, "error": str(exc)})

    return results, all_telemetry_rows, all_alert_records, all_health_records, publish_items, errors


@router.post("/ingest/batch")
async def ingest_batch(
    readings: list[TelemetryReading],
    request: Request,
):
    """
    Receive a batch of TelemetryReadings.
    CPU work runs in a thread pool. DB writes go to background DbWriter.
    Redis publishes use a pipeline (single round-trip).
    """
    writer: DbWriter = request.app.state.db_writer

    # ── Run CPU-bound work off the event loop ──
    loop = asyncio.get_event_loop()
    results, telemetry_rows, alert_records, health_records, publish_items, errors = await loop.run_in_executor(
        None, _process_readings_sync, readings
    )

    # ── Enqueue DB writes to background worker (non-blocking) ──
    writer.put(telemetry_rows, alert_records, health_records)

    # ── Redis pipeline: all publishes in one round-trip ──
    if publish_items:
        redis_client = get_redis_raw()
        pipe = redis_client.pipeline(transaction=False)
        for channel, payload in publish_items:
            pipe.publish(channel, payload)
        await pipe.execute()

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
