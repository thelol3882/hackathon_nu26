"""Telemetry ingest endpoints (single + batch).

Per reading: EMA-filter & flatten, evaluate alerts, calculate health, then
fan out to Redis Pub/Sub (live feed) and Redis Streams (DB Writer persistence).
"""

import asyncio

from fastapi import APIRouter

from processor.api.dependencies import Redis
from processor.core.redis_client import get_redis_raw, publish_alert, publish_health, publish_telemetry
from processor.services.alert_evaluator import evaluate_alerts
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
from shared.streams import ALERTS_STREAM, HEALTH_STREAM, TELEMETRY_STREAM, xadd_rows
from shared.utils import generate_id
from shared.wire import encode as wire_encode

logger = get_logger(__name__)

router = APIRouter()


async def _process_single(
    reading: TelemetryReading,
    redis_client,
) -> dict:
    """Run the full ingest pipeline for one reading; returns a response summary."""
    loco_id = str(reading.locomotive_id)

    # flatten_reading mutates sensor.value in place to the filtered value;
    # evaluate_alerts relies on that mutation.
    telemetry_dicts = flatten_reading(reading)

    alert_events = evaluate_alerts(reading)

    alert_dicts = [
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
            "recommendation": ae.recommendation,
            "timestamp": ae.timestamp,
            "acknowledged": ae.acknowledged,
        }
        for ae in alert_events
    ]

    health = calculate_health(reading)

    health_dicts = [
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
    ]

    telemetry_ingested_total.labels(locomotive_type=reading.locomotive_type.value).inc(len(reading.sensors))
    health_index_calculated_total.inc()
    health_index_value.labels(locomotive_id=loco_id, locomotive_type=reading.locomotive_type.value).set(
        health.overall_score
    )
    for ae in alert_events:
        alerts_fired_total.labels(severity=ae.severity.value, sensor_type=str(ae.sensor_type)).inc()

    telemetry_payload = wire_encode(reading.model_dump(mode="json"))
    health_payload = wire_encode(health.model_dump(mode="json"))
    alert_payloads = [wire_encode(ae.model_dump(mode="json")) for ae in alert_events]

    pubsub_tasks = [
        publish_telemetry(loco_id, telemetry_payload),
        publish_health(loco_id, health_payload),
    ]
    pubsub_tasks += [publish_alert(ap) for ap in alert_payloads]

    stream_tasks = [
        xadd_rows(redis_client, TELEMETRY_STREAM, telemetry_dicts),
        xadd_rows(redis_client, ALERTS_STREAM, alert_dicts),
        xadd_rows(redis_client, HEALTH_STREAM, health_dicts),
    ]

    await asyncio.gather(*pubsub_tasks, *stream_tasks, return_exceptions=True)

    return {
        "locomotive_id": loco_id,
        "rows_written": len(telemetry_dicts),
        "alerts_raised": len(alert_events),
        "health_score": health.overall_score,
        "health_category": health.category,
    }


@router.post("/ingest")
async def ingest_telemetry(
    reading: TelemetryReading,
    redis: Redis,
):
    """Receive a single TelemetryReading and run the full processing pipeline."""
    logger.info(
        "Ingest request received",
        locomotive_id=str(reading.locomotive_id),
        sensor_count=len(reading.sensors),
    )
    result = await _process_single(reading, redis)
    return {"status": "accepted", **result}


def _process_readings_sync(
    readings: list[TelemetryReading],
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[tuple[str, bytes]], list[dict]]:
    """CPU-bound batch processing; returns plain dicts safe to hand off across threads."""
    results: list[dict] = []
    errors: list[dict] = []
    all_telemetry_rows: list[dict] = []
    all_alert_records: list[dict] = []
    all_health_records: list[dict] = []
    publish_items: list[tuple[str, bytes]] = []

    for reading in readings:
        loco_id = str(reading.locomotive_id)
        try:
            rows = flatten_reading(reading)

            all_telemetry_rows.extend(rows)

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
                    "recommendation": ae.recommendation,
                    "timestamp": ae.timestamp,
                    "acknowledged": ae.acknowledged,
                }
                for ae in alert_events
            )

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

            telemetry_ingested_total.labels(locomotive_type=reading.locomotive_type.value).inc(len(reading.sensors))
            health_index_calculated_total.inc()
            health_index_value.labels(locomotive_id=loco_id, locomotive_type=reading.locomotive_type.value).set(
                health.overall_score
            )
            for ae in alert_events:
                alerts_fired_total.labels(severity=ae.severity.value, sensor_type=str(ae.sensor_type)).inc()

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
):
    """Batch ingest: CPU work runs in a thread pool; pub/sub uses a pipeline."""
    loop = asyncio.get_event_loop()
    results, telemetry_rows, alert_records, health_records, publish_items, errors = await loop.run_in_executor(
        None, _process_readings_sync, readings
    )

    redis_client = get_redis_raw()

    stream_tasks = [
        xadd_rows(redis_client, TELEMETRY_STREAM, telemetry_rows),
        xadd_rows(redis_client, ALERTS_STREAM, alert_records),
        xadd_rows(redis_client, HEALTH_STREAM, health_records),
    ]
    await asyncio.gather(*stream_tasks, return_exceptions=True)

    if publish_items:
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
