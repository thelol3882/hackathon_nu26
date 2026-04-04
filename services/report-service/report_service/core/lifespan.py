from contextlib import asynccontextmanager

from fastapi import FastAPI

from report_service.core.database import close_db_pool, init_db_pool
from shared.observability import setup_observability


@asynccontextmanager
async def lifespan(app: FastAPI):
    shutdown_otel = setup_observability(app, service_name="report-service")
    await init_db_pool()
    yield
    await close_db_pool()
    shutdown_otel()
