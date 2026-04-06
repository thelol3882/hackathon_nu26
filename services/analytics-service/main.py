"""Analytics Service entry point.

Runs concurrently: gRPC server, HTTP server (Prometheus /metrics + /health),
fleet aggregator, and per-locomotive health cache listener. The extra HTTP
server exists because Prometheus cannot scrape gRPC.
"""

import asyncio
import signal
import sys

import grpc.aio
import uvicorn
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI

from analytics.aggregator import FleetAggregator
from analytics.background.health_cache import run_health_cache
from analytics.core.config import get_settings
from analytics.core.database import close_db_pool, init_db_pool
from analytics.core.redis_client import close_redis, get_redis_raw, init_redis
from analytics.servicer import AnalyticsServicer
from shared.generated import telemetry_pb2_grpc
from shared.observability import get_logger, setup_observability
from shared.observability.prometheus import setup_prometheus

logger = get_logger(__name__)


async def serve_grpc(port: int) -> grpc.aio.Server:
    """Start the async gRPC server on the shared asyncio loop."""
    server = grpc.aio.server(
        options=[
            ("grpc.max_receive_message_length", 10 * 1024 * 1024),
            ("grpc.max_send_message_length", 10 * 1024 * 1024),
        ],
    )

    telemetry_pb2_grpc.add_AnalyticsServiceServicer_to_server(
        AnalyticsServicer(),
        server,
    )

    server.add_insecure_port(f"0.0.0.0:{port}")
    await server.start()
    logger.info("gRPC server started", port=port)
    return server


def _run_migrations() -> None:
    """Apply pending Alembic migrations (this service owns the schema)."""
    import pathlib

    ini_path = pathlib.Path(__file__).resolve().parent / "alembic.ini"
    alembic_cfg = AlembicConfig(str(ini_path))
    alembic_command.upgrade(alembic_cfg, "head")


async def main() -> None:
    settings = get_settings()

    await init_db_pool()
    await init_redis()

    redis_raw = get_redis_raw()

    health_task = asyncio.create_task(
        run_health_cache(redis_raw),
        name="health-cache",
    )

    aggregator = FleetAggregator(redis_raw)
    aggregator_task = asyncio.create_task(
        aggregator.run(),
        name="fleet-aggregator",
    )
    logger.info("Fleet aggregator started")

    grpc_server = await serve_grpc(settings.grpc_port)

    metrics_app = FastAPI(title="Analytics Service Metrics")
    shutdown_otel = setup_observability(metrics_app, service_name=settings.service_name)
    setup_prometheus(metrics_app, service_name=settings.service_name)

    @metrics_app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "fleet_aggregator_size": aggregator.fleet_size,
        }

    config = uvicorn.Config(
        metrics_app,
        host="0.0.0.0",
        port=settings.http_port,
        log_level="warning",
    )
    http_server = uvicorn.Server(config)

    stop_event = asyncio.Event()

    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop_event.set)

    http_task = asyncio.create_task(http_server.serve())

    if sys.platform == "win32":
        # asyncio signal handlers don't work on Windows; rely on uvicorn's Ctrl+C.
        await http_task
    else:
        await stop_event.wait()

    logger.info("Shutting down...")
    aggregator.stop()
    aggregator_task.cancel()
    health_task.cancel()
    await grpc_server.stop(grace=5)
    http_server.should_exit = True
    await http_task
    await close_redis()
    await close_db_pool()
    shutdown_otel()
    logger.info("Analytics service stopped")


if __name__ == "__main__":
    # Alembic env.py uses asyncio.run() internally, so migrations must run
    # before we enter the main event loop.
    logger.info("Running Alembic migrations...")
    _run_migrations()
    logger.info("Migrations complete")

    asyncio.run(main())
