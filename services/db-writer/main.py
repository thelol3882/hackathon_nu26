"""
DB Writer service entry point.

Runs three StreamConsumer instances concurrently (asyncio tasks),
one per stream: telemetry, alerts, health.

No primary HTTP server — this is a pure background worker.
A minimal FastAPI app runs on a separate port solely for the
Prometheus /metrics endpoint.
"""

from __future__ import annotations

import asyncio
import signal

import uvicorn
from fastapi import FastAPI

from db_writer.core.config import get_settings
from db_writer.core.database import close_db_pool, get_session_factory, init_db_pool
from db_writer.core.redis_client import close_redis, get_redis_raw, init_redis
from db_writer.models.alert_entity import AlertRecord
from db_writer.models.health_entity import HealthSnapshotRecord
from db_writer.models.telemetry_entity import TelemetryRecord
from db_writer.services.stream_consumer import StreamConsumer
from shared.observability import setup_observability
from shared.observability.prometheus import setup_prometheus
from shared.streams import ALERTS_STREAM, HEALTH_STREAM, TELEMETRY_STREAM

# Minimal FastAPI app for Prometheus /metrics endpoint only
metrics_app = FastAPI(title="DB Writer Metrics", docs_url=None, redoc_url=None)
shutdown_otel = setup_observability(metrics_app, service_name="db-writer")
setup_prometheus(metrics_app, service_name="db-writer")


async def main() -> None:
    settings = get_settings()

    await init_db_pool()
    await init_redis()

    session_factory = get_session_factory()
    redis_client = get_redis_raw()

    # Create one consumer per stream
    consumers = [
        StreamConsumer(
            redis_client, session_factory, TELEMETRY_STREAM,
            settings.consumer_name, TelemetryRecord,
        ),
        StreamConsumer(
            redis_client, session_factory, ALERTS_STREAM,
            settings.consumer_name, AlertRecord,
        ),
        StreamConsumer(
            redis_client, session_factory, HEALTH_STREAM,
            settings.consumer_name, HealthSnapshotRecord,
        ),
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

    # Periodic lag metric update (every 15 seconds)
    async def _update_lag_loop():
        while True:
            for c in consumers:
                await c.update_lag()
            await asyncio.sleep(15.0)

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
