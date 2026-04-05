from contextlib import asynccontextmanager

from fastapi import FastAPI

from processor.core.database import close_db_pool, init_db_pool
from processor.core.redis_client import close_redis, init_redis
from processor.services.db_writer import DbWriter


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    await init_redis()
    writer = DbWriter()
    await writer.start()
    app.state.db_writer = writer
    yield
    await writer.stop()
    await close_redis()
    await close_db_pool()
    app.state.shutdown_otel()
