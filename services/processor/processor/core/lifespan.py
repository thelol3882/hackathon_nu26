from contextlib import asynccontextmanager

from fastapi import FastAPI

from processor.core.database import close_db_pool, init_db_pool
from processor.core.redis_client import close_redis, init_redis
from shared.observability import setup_observability


@asynccontextmanager
async def lifespan(app: FastAPI):
    shutdown_otel = setup_observability(app, service_name="processor")
    await init_db_pool()
    await init_redis()
    yield
    await close_redis()
    await close_db_pool()
    shutdown_otel()
