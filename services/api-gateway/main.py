from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_gateway.api.router_alerts import router as alerts_router
from api_gateway.api.router_auth import router as auth_router
from api_gateway.api.router_config import router as config_router
from api_gateway.api.router_health import router as health_router
from api_gateway.api.router_locomotives import router as locomotives_router
from api_gateway.api.router_reports import router as reports_router
from api_gateway.api.router_telemetry import router as telemetry_router
from api_gateway.api.router_ws_ticket import router as ws_ticket_router
from api_gateway.core.auth import get_current_user, require_admin
from api_gateway.core.config import get_settings
from api_gateway.core.lifespan import lifespan, run_migrations
from api_gateway.core.middleware import UserContextMiddleware
from shared.observability import setup_observability
from shared.observability.prometheus import setup_prometheus

app = FastAPI(
    title="Locomotive Digital Twin — API Gateway",
    description="Real-time telemetry streaming, health index, and fleet management API.",
    version="0.1.0",
    lifespan=lifespan,
    root_path="/api",
)

settings = get_settings()
app.state.shutdown_otel = setup_observability(app, service_name="api-gateway")
setup_prometheus(app, service_name="api-gateway")
app.add_middleware(UserContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes (no auth)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(health_router, tags=["health"])

# Protected routes (require JWT)
_auth = [Depends(get_current_user)]
app.include_router(ws_ticket_router, tags=["websocket"], dependencies=_auth)
app.include_router(locomotives_router, prefix="/locomotives", tags=["locomotives"], dependencies=_auth)
app.include_router(telemetry_router, prefix="/telemetry", tags=["telemetry"], dependencies=_auth)
app.include_router(alerts_router, prefix="/alerts", tags=["alerts"], dependencies=_auth)
app.include_router(reports_router, prefix="/reports", tags=["reports"], dependencies=_auth)

# Admin-only routes
_admin = [Depends(require_admin)]
app.include_router(config_router, prefix="/config", tags=["config"], dependencies=_admin)

if __name__ == "__main__":
    import uvicorn

    # Run migrations BEFORE the async event loop starts.
    # alembic env.py uses asyncio.run() internally, which can't nest.
    run_migrations()

    uvicorn.run(app, host="0.0.0.0", port=8000)
