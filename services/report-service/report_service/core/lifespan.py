from contextlib import asynccontextmanager

from fastapi import FastAPI

from report_service.core.config import get_settings
from report_service.core.database import close_db_pool, init_db_pool
from report_service.core.rabbitmq import close_rabbitmq, init_rabbitmq, start_consuming
from report_service.services.report_worker import process_report_job, set_analytics_client
from shared.grpc_client import AnalyticsClient
from shared.log_codes import INFRA_SHUTDOWN, INFRA_STARTUP
from shared.observability import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Connect to Analytics Service via gRPC for telemetry queries.
    # Report Service no longer accesses TimescaleDB directly.
    analytics = AnalyticsClient(
        settings.analytics_grpc_target,
        timeout=settings.analytics_grpc_timeout,
    )
    await analytics.connect()
    app.state.analytics = analytics
    set_analytics_client(analytics)

    await init_db_pool()  # PostgreSQL for generated_reports table
    await init_rabbitmq()
    await start_consuming(process_report_job)
    logger.info("Report service started", code=INFRA_STARTUP)
    yield
    logger.info("Report service shutting down", code=INFRA_SHUTDOWN)
    await close_rabbitmq()
    await close_db_pool()
    await analytics.close()
    app.state.shutdown_otel()
