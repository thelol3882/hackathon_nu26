"""Analytics Service entry point.

ARCHITECTURE:
  This service runs THREE concurrent subsystems:

  1. gRPC server (port 50051) — handles RPC calls from API Gateway
     and Report Service. This is the primary query interface.

  2. HTTP server (port 8020) — serves Prometheus /metrics and a /health
     endpoint for Docker/Kubernetes readiness probes.

  3. Fleet aggregator — background task that subscribes to health:live:*,
     maintains in-memory fleet state, and publishes fleet:summary +
     fleet:changes to Redis Pub/Sub for the fleet dashboard.

  Plus the existing health cache listener (caches individual locomotive
  health indices from processor pub/sub into Redis keys).

  WHY TWO SERVERS:
    gRPC uses HTTP/2 with binary protobuf — Prometheus can't scrape it.
    Prometheus expects plain HTTP GET /metrics with text/plain response.
    So we run a tiny FastAPI app alongside for observability only.
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
    """Start the async gRPC server.

    grpc.aio.server() creates an async server that integrates with
    Python's asyncio event loop — same loop as FastAPI/uvicorn.
    """
    server = grpc.aio.server(
        options=[
            # Max inbound message: 10 MB
            ("grpc.max_receive_message_length", 10 * 1024 * 1024),
            ("grpc.max_send_message_length", 10 * 1024 * 1024),
        ],
    )

    # Register the service implementation
    telemetry_pb2_grpc.add_AnalyticsServiceServicer_to_server(
        AnalyticsServicer(),
        server,
    )

    # Listen on all interfaces (0.0.0.0) inside Docker
    server.add_insecure_port(f"0.0.0.0:{port}")
    await server.start()
    logger.info("gRPC server started", port=port)
    return server


def _run_migrations() -> None:
    """Apply pending Alembic migrations before accepting traffic.

    Analytics Service owns the TimescaleDB schema — tables, hypertables,
    continuous aggregates, retention and compression policies are all
    managed here.  DB Writer only does INSERT.
    """
    import pathlib

    ini_path = pathlib.Path(__file__).resolve().parent / "alembic.ini"
    alembic_cfg = AlembicConfig(str(ini_path))
    alembic_command.upgrade(alembic_cfg, "head")


async def main() -> None:
    settings = get_settings()

    # Apply migrations before anything else — DB Writer depends on
    # tables being ready.
    logger.info("Running Alembic migrations...")
    _run_migrations()
    logger.info("Migrations complete")

    # Initialize infrastructure
    await init_db_pool()
    await init_redis()

    redis_raw = get_redis_raw()

    # Background task: cache individual locomotive health from pub/sub
    health_task = asyncio.create_task(
        run_health_cache(redis_raw),
        name="health-cache",
    )

    # Background task: fleet aggregator — subscribes to health:live:*,
    # maintains in-memory state of all 1700 locos, publishes fleet:summary
    # and fleet:changes every 2 seconds for the fleet dashboard.
    aggregator = FleetAggregator(redis_raw)
    aggregator_task = asyncio.create_task(
        aggregator.run(),
        name="fleet-aggregator",
    )
    logger.info("Fleet aggregator started")

    # Start gRPC server
    grpc_server = await serve_grpc(settings.grpc_port)

    # Start HTTP server for Prometheus /metrics and health checks
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

    # Graceful shutdown handling
    stop_event = asyncio.Event()

    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop_event.set)

    # Run HTTP server in a task so we can await the stop event
    http_task = asyncio.create_task(http_server.serve())

    if sys.platform == "win32":
        # On Windows, signal handlers don't work with asyncio.
        # Just wait for the HTTP server (Ctrl+C stops uvicorn directly).
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
    asyncio.run(main())
