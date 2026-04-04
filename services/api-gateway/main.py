from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_gateway.api.router_alerts import router as alerts_router
from api_gateway.api.router_health import router as health_router
from api_gateway.api.router_locomotives import router as locomotives_router
from api_gateway.api.router_telemetry import router as telemetry_router
from api_gateway.api.ws_telemetry import router as ws_router
from api_gateway.core.config import get_settings
from api_gateway.core.lifespan import lifespan

app = FastAPI(title="Locomotive Telemetry API Gateway", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(locomotives_router, prefix="/locomotives", tags=["locomotives"])
app.include_router(telemetry_router, prefix="/telemetry", tags=["telemetry"])
app.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
app.include_router(ws_router, tags=["websocket"])
app.include_router(health_router, tags=["health"])
