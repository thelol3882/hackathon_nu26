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


def run_migrations() -> None:
    """Apply pending Alembic migrations.

    Must be called before the async event loop starts because alembic env.py
    internally calls asyncio.run() which cannot nest inside a running loop.
    """
    ini_path = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"
    alembic_cfg = AlembicConfig(str(ini_path))
    alembic_command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    await init_app_db()
    await init_redis()
    await init_rabbitmq()

    analytics = AnalyticsClient(
        settings.analytics_grpc_target,
        timeout=settings.analytics_grpc_timeout,
    )
    await analytics.connect()
    app.state.analytics = analytics

    report_client = ReportClient(
        settings.report_grpc_target,
        timeout=settings.report_grpc_timeout,
    )
    await report_client.connect()
    app.state.report_client = report_client

    redis_client = get_redis()
    app_session_factory = get_app_session_factory()

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
