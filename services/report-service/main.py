from fastapi import FastAPI

from report_service.api.router_analytics import router as analytics_router
from report_service.api.router_health import router as health_router
from report_service.api.router_health_index import router as health_index_router
from report_service.api.router_reports import router as reports_router
from report_service.core.lifespan import lifespan

app = FastAPI(title="Locomotive Report Service", lifespan=lifespan)

app.include_router(reports_router, prefix="/reports", tags=["reports"])
app.include_router(health_index_router, prefix="/health-index", tags=["health-index"])
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
app.include_router(health_router, tags=["health"])
