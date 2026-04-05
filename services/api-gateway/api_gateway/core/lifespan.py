import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api_gateway.background.health_cache import run_health_cache
from api_gateway.core.config import get_settings
from api_gateway.core.database import close_db_pool, get_session_factory, init_db_pool
from api_gateway.core.rabbitmq import close_rabbitmq, init_rabbitmq
from api_gateway.core.redis_client import close_redis, get_redis, get_redis_raw, init_redis
from api_gateway.services.health_service import init_health_config
from api_gateway.services.seed import seed_admin_user, seed_locomotives


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()

    await init_db_pool()
    await init_redis()
    await init_rabbitmq()

    redis_client = get_redis()
    redis_raw = get_redis_raw()
    session_factory = get_session_factory()

    # Seed default data and health config
    async with session_factory() as session:
        await seed_admin_user(session)
        await seed_locomotives(session)
        await init_health_config(session, redis_client)

    # Background: cache health index from processor via Redis pub/sub
    health_task = asyncio.create_task(
        run_health_cache(redis_raw),
        name="health-cache",
    )

    yield

    health_task.cancel()
    await close_rabbitmq()
    await close_redis()
    await close_db_pool()
    app.state.shutdown_otel()
