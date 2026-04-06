"""WebSocket server: streams Redis pub/sub messages to WebSocket clients.

Has no database, no JWT decoding (auth via one-time Redis tickets), and no
business logic — the event loop only handles Redis fan-out and heartbeats.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.observability import setup_observability
from shared.observability.prometheus import setup_prometheus
from ws_server.connection_manager import ConnectionManager
from ws_server.core.config import get_settings
from ws_server.core.redis_client import close_redis, get_redis_raw, init_redis
from ws_server.handler import router, set_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_redis()

    manager = ConnectionManager(
        redis_client=get_redis_raw(),
        max_connections=settings.max_connections,
    )
    await manager.start()
    set_manager(manager)

    yield

    await manager.shutdown()
    await close_redis()
    app.state.shutdown_otel()


app = FastAPI(
    title="Locomotive Digital Twin — WebSocket Server",
    description="Real-time telemetry streaming via WebSocket.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.shutdown_otel = setup_observability(app, service_name="ws-server")
setup_prometheus(app, service_name="ws-server")

app.include_router(router)
