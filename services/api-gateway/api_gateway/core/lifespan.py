import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api_gateway.core.config import get_settings
from api_gateway.core.database import close_db_pool, get_session_factory, init_db_pool
from api_gateway.core.rabbitmq import close_rabbitmq, init_rabbitmq
from api_gateway.core.redis_client import close_redis, get_redis, get_redis_raw, init_redis
from api_gateway.services.alert_service import run_alert_persistence
from api_gateway.services.connection_manager import ConnectionManager
from api_gateway.services.health_service import init_health_config, run_health_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    await init_db_pool()
    await init_redis()
    await init_rabbitmq()

    redis_client = get_redis()
    redis_raw = get_redis_raw()
    session_factory = get_session_factory()

    # Seed health config: DB → Redis cache
    async with session_factory() as session:
        await init_health_config(session, redis_client)

    # WebSocket connection manager (uses raw client for binary-safe pub/sub)
    manager = ConnectionManager(
        redis_client=redis_raw,
        max_connections=settings.ws_max_connections,
    )
    await manager.start()
    app.state.ws_manager = manager

    # Background: persist alerts from Redis to DB (raw client for binary pub/sub)
    alert_task = asyncio.create_task(
        run_alert_persistence(redis_raw, session_factory),
        name="alert-persistence",
    )

    # Background: cache health index from processor via Redis pub/sub
    health_task = asyncio.create_task(
        run_health_cache(redis_raw),
        name="health-cache",
    )

    yield

    health_task.cancel()
    alert_task.cancel()
    await manager.shutdown()
    await close_rabbitmq()
    await close_redis()
    await close_db_pool()
    app.state.shutdown_otel()
