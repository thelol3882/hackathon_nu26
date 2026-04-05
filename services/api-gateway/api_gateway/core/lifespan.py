import pathlib
from contextlib import asynccontextmanager

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI

from api_gateway.core.config import get_settings
from api_gateway.core.database import close_app_db, get_app_session_factory, init_app_db
from api_gateway.core.rabbitmq import close_rabbitmq, init_rabbitmq
from api_gateway.core.redis_client import close_redis, get_redis, init_redis
from api_gateway.services.health_service import init_health_config
from api_gateway.services.seed import seed_admin_user, seed_locomotives
from shared.grpc_client import AnalyticsClient, ReportClient
from shared.observability import get_logger

_logger = get_logger(__name__)


def _run_migrations() -> None:
    ini_path = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"
    alembic_cfg = AlembicConfig(str(ini_path))
    alembic_command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    _logger.info("Running Alembic migrations...")
    _run_migrations()
    _logger.info("Migrations complete")

    await init_app_db()  # PostgreSQL for CRUD
    await init_redis()
    await init_rabbitmq()

    # Connect to Analytics Service via gRPC.
    # All telemetry, alert, and health queries go through this client.
    analytics = AnalyticsClient(
        settings.analytics_grpc_target,
        timeout=settings.analytics_grpc_timeout,
    )
    await analytics.connect()
    app.state.analytics = analytics

    # Connect to Report Service via gRPC for report queries.
    report_client = ReportClient(
        settings.report_grpc_target,
        timeout=settings.report_grpc_timeout,
    )
    await report_client.connect()
    app.state.report_client = report_client

    redis_client = get_redis()
    app_session_factory = get_app_session_factory()

    # Seed default data and health config (all in PostgreSQL)
    async with app_session_factory() as session:
        await seed_admin_user(session)
        await seed_locomotives(session)
        await init_health_config(session, redis_client)

    yield

    await report_client.close()
    await analytics.close()
    await close_rabbitmq()
    await close_redis()
    await close_app_db()
    app.state.shutdown_otel()
