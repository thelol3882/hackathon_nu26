from contextlib import asynccontextmanager

from fastapi import FastAPI

from processor.core.database import close_db_pool, init_db_pool
from processor.core.redis_client import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db_pool()
    await init_redis()
    yield
    # Shutdown
    await close_redis()
    await close_db_pool()
