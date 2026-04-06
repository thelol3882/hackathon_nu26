"""
DB Writer service entry point.

Runs three StreamConsumer instances concurrently (asyncio tasks), one per
stream: telemetry, alerts, health. Each consumer runs its own reader +
worker-pool pipeline with COPY-based bulk loads through per-worker
UNLOGGED staging tables.

No primary HTTP server — this is a pure background worker. A minimal
FastAPI app runs on a separate port solely for the Prometheus /metrics
endpoint.
"""

from __future__ import annotations

import asyncio
import re
import signal

import uvicorn
from fastapi import FastAPI

from db_writer.core.config import get_settings
from db_writer.core.database import close_db_pool, get_pool, init_db_pool
from db_writer.core.redis_client import close_redis, get_redis_raw, init_redis
from db_writer.models.alert_entity import AlertRecord
from db_writer.models.health_entity import HealthSnapshotRecord
from db_writer.models.telemetry_entity import TelemetryRecord
from db_writer.services.stream_consumer import StreamConsumer
from shared.observability import get_logger, setup_observability
from shared.observability.prometheus import setup_prometheus
from shared.streams import (
    ALERTS_STREAM,
    HEALTH_STREAM,
    READER_BATCH_SIZE_DEFAULT,
    READER_BATCH_SIZE_TELEMETRY,
    TELEMETRY_STREAM,
)

logger = get_logger(__name__)

# Minimal FastAPI app for Prometheus /metrics endpoint only
metrics_app = FastAPI(title="DB Writer Metrics", docs_url=None, redoc_url=None)
shutdown_otel = setup_observability(metrics_app, service_name="db-writer")
setup_prometheus(metrics_app, service_name="db-writer")


def _sanitize(name: str) -> str:
    """Make a string safe to embed in a SQL identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _staging_tables_for(target_table: str, consumer_name: str, worker_count: int) -> list[str]:
    """Generate per-worker staging table names for a target table."""
    safe = _sanitize(consumer_name)
    return [f"{target_table}_staging_{safe}_{i}" for i in range(worker_count)]


async def _bootstrap_staging(all_staging: list[tuple[str, str]]) -> None:
    """Create UNLOGGED staging tables and TRUNCATE any leftovers.

    Args:
        all_staging: list of (staging_name, target_name) tuples.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        for staging, target in all_staging:
            await conn.execute(
                f'CREATE UNLOGGED TABLE IF NOT EXISTS "{staging}" '
                f'(LIKE "{target}" INCLUDING DEFAULTS '
                f"EXCLUDING CONSTRAINTS EXCLUDING INDEXES EXCLUDING STATISTICS)"
            )
            # Clear any rows left behind by a crashed transaction.
            await conn.execute(f'TRUNCATE TABLE "{staging}"')
    logger.info("Staging tables ready", count=len(all_staging))


async def main() -> None:
    settings = get_settings()

    await init_db_pool()
    await init_redis()

    pg_pool = get_pool()
    redis_client = get_redis_raw()

    # Per-stream worker counts from settings.
    stream_specs = [
        (
            TELEMETRY_STREAM,
            TelemetryRecord,
            settings.writer_workers_telemetry,
            READER_BATCH_SIZE_TELEMETRY,
        ),
        (
            ALERTS_STREAM,
            AlertRecord,
            settings.writer_workers_alerts,
            READER_BATCH_SIZE_DEFAULT,
        ),
        (
            HEALTH_STREAM,
            HealthSnapshotRecord,
            settings.writer_workers_health,
            READER_BATCH_SIZE_DEFAULT,
        ),
    ]

    # Compute staging table names and create them before starting consumers.
    all_staging: list[tuple[str, str]] = []
    per_consumer_staging: dict[str, list[str]] = {}
    for stream_name, model, workers, _reader_bs in stream_specs:
        staging = _staging_tables_for(model.__tablename__, settings.consumer_name, workers)
        per_consumer_staging[stream_name] = staging
        all_staging.extend((s, model.__tablename__) for s in staging)
    await _bootstrap_staging(all_staging)

    # Create one consumer per stream.
    consumers = [
        StreamConsumer(
            redis_client=redis_client,
            pg_pool=pg_pool,
            stream=stream_name,
            consumer_name=settings.consumer_name,
            model_class=model,
            staging_tables=per_consumer_staging[stream_name],
            reader_batch_size=reader_bs,
            rows_per_flush=settings.rows_per_flush,
            queue_maxsize=settings.queue_maxsize,
        )
        for stream_name, model, _workers, reader_bs in stream_specs
    ]

    # Start metrics HTTP server in background
    config = uvicorn.Config(
        metrics_app,
        host="0.0.0.0",
        port=settings.metrics_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    metrics_task = asyncio.create_task(server.serve(), name="metrics-server")

    # Run all consumers concurrently
    consumer_tasks = [asyncio.create_task(c.start(), name=f"consumer-{c._stream}") for c in consumers]

    # Periodic lag metric update (every 5 seconds — more responsive than 15s
    # so burst detection in Grafana doesn't lag behind reality)
    async def _update_lag_loop():
        while True:
            for c in consumers:
                await c.update_lag()
            await asyncio.sleep(5.0)

    lag_task = asyncio.create_task(_update_lag_loop(), name="lag-updater")

    # Graceful shutdown on SIGTERM/SIGINT
    stop_event = asyncio.Event()

    def _signal_handler():
        for c in consumers:
            c.stop()
        server.should_exit = True
        lag_task.cancel()
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    # Wait for either stop signal or consumer exit
    await stop_event.wait()

    # Give consumers time to finish current batch
    for t in consumer_tasks:
        t.cancel()
    await asyncio.gather(*consumer_tasks, metrics_task, lag_task, return_exceptions=True)

    await close_redis()
    await close_db_pool()
    shutdown_otel()


if __name__ == "__main__":
    asyncio.run(main())
