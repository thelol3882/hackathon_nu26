from contextlib import asynccontextmanager

from fastapi import FastAPI

from report_service.core.database import close_db_pool, init_db_pool
from report_service.core.rabbitmq import close_rabbitmq, init_rabbitmq, start_consuming
from report_service.services.report_worker import process_report_job
from shared.log_codes import INFRA_SHUTDOWN, INFRA_STARTUP
from shared.observability import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    await init_rabbitmq()
    await start_consuming(process_report_job)
    logger.info("Report service started", code=INFRA_STARTUP)
    yield
    logger.info("Report service shutting down", code=INFRA_SHUTDOWN)
    await close_rabbitmq()
    await close_db_pool()
    app.state.shutdown_otel()
