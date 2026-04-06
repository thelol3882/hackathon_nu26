from contextlib import asynccontextmanager

from fastapi import FastAPI

from processor.core.redis_client import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    await close_redis()
    app.state.shutdown_otel()
