"""Report Service entry point.

Runs three concurrent subsystems: gRPC server (report queries), HTTP server
(sync reports, health-index, analytics, Prometheus /metrics), and a RabbitMQ
consumer for async report jobs. The HTTP server exists alongside gRPC because
Prometheus cannot scrape HTTP/2 binary protobuf.
"""

import asyncio
import pathlib
import signal
import sys

import grpc.aio
import uvicorn
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI

from report_service.api.router_analytics import router as analytics_router
from report_service.api.router_health import router as health_router
from report_service.api.router_health_index import router as health_index_router
from report_service.api.router_reports import router as reports_router
from report_service.core.config import get_settings
from report_service.core.database import close_db_pool, init_db_pool
from report_service.core.rabbitmq import close_rabbitmq, init_rabbitmq, start_consuming
from report_service.servicer import ReportServicer
from report_service.services.report_worker import process_report_job, set_analytics_client
from shared.generated import report_pb2_grpc
from shared.grpc_client import AnalyticsClient
from shared.log_codes import INFRA_SHUTDOWN, INFRA_STARTUP
from shared.observability import get_logger, setup_observability
from shared.observability.prometheus import setup_prometheus

logger = get_logger(__name__)


def _run_migrations() -> None:
    """Apply pending Alembic migrations before accepting traffic."""
    ini_path = pathlib.Path(__file__).resolve().parent / "alembic.ini"
    alembic_cfg = AlembicConfig(str(ini_path))
    alembic_command.upgrade(alembic_cfg, "head")


async def serve_grpc(port: int) -> grpc.aio.Server:
    """Start the async gRPC server for report queries."""
    server = grpc.aio.server(
        options=[
            ("grpc.max_receive_message_length", 10 * 1024 * 1024),
            ("grpc.max_send_message_length", 10 * 1024 * 1024),
        ],
    )
    report_pb2_grpc.add_ReportServiceServicer_to_server(
        ReportServicer(),
        server,
    )
    server.add_insecure_port(f"0.0.0.0:{port}")
    await server.start()
    logger.info("gRPC server started", port=port)
    return server


async def main() -> None:
    settings = get_settings()

    await init_db_pool()
    await init_rabbitmq()

    analytics = AnalyticsClient(
        settings.analytics_grpc_target,
        timeout=settings.analytics_grpc_timeout,
    )
    await analytics.connect()
    set_analytics_client(analytics)

    await start_consuming(process_report_job)

    grpc_server = await serve_grpc(settings.grpc_port)

    http_app = FastAPI(title="Locomotive Report Service")
    shutdown_otel = setup_observability(http_app, service_name="report-service")
    setup_prometheus(http_app, service_name="report-service")

    http_app.state.analytics = analytics

    http_app.include_router(reports_router, prefix="/reports", tags=["reports"])
    http_app.include_router(health_index_router, prefix="/health-index", tags=["health-index"])
    http_app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
    http_app.include_router(health_router, tags=["health"])

    config = uvicorn.Config(
        http_app,
        host="0.0.0.0",
        port=8002,
        log_level="warning",
    )
    http_server = uvicorn.Server(config)

    stop_event = asyncio.Event()

    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop_event.set)

    http_task = asyncio.create_task(http_server.serve())
    logger.info("Report service started", code=INFRA_STARTUP)

    if sys.platform == "win32":
        await http_task
    else:
        await stop_event.wait()

    logger.info("Shutting down...", code=INFRA_SHUTDOWN)
    await grpc_server.stop(grace=5)
    http_server.should_exit = True
    await http_task
    await close_rabbitmq()
    await close_db_pool()
    await analytics.close()
    shutdown_otel()
    logger.info("Report service stopped")


if __name__ == "__main__":
    # Must run before the async event loop: Alembic env.py uses asyncio.run()
    # internally, which can't nest inside another running loop.
    logger.info("Running Alembic migrations...")
    _run_migrations()
    logger.info("Migrations complete")

    asyncio.run(main())
