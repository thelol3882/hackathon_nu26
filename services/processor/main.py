from fastapi import FastAPI

from processor.api.router_health import router as health_router
from processor.api.router_ingest import router as ingest_router
from processor.core.lifespan import lifespan

app = FastAPI(title="Locomotive Telemetry Processor", lifespan=lifespan)

app.include_router(ingest_router, prefix="/telemetry", tags=["telemetry"])
app.include_router(health_router, tags=["health"])
