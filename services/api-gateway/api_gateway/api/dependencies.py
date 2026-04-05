"""FastAPI dependencies for database sessions, gRPC client, and Redis.

Database sessions:
  AppSession — PostgreSQL, for auth / CRUD / config operations

gRPC client:
  Analytics — AnalyticsClient for telemetry, alerts, and health queries.
  Replaces the old TsSession (direct TimescaleDB access).

Routers pick the right dependency:
  router_auth, router_locomotives (CRUD), router_reports, router_config → AppSession
  router_telemetry, router_alerts, router_locomotives (health) → Analytics
"""

from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.core.config import GatewaySettings, get_settings
from api_gateway.core.database import get_app_db_session
from api_gateway.core.redis_client import get_redis
from shared.grpc_client import AnalyticsClient, ReportClient

Settings = Annotated[GatewaySettings, Depends(get_settings)]

# PostgreSQL — auth, locomotives, health config
AppSession = Annotated[AsyncSession, Depends(get_app_db_session)]

# Backward-compatible alias
DbSession = AppSession

Redis = Annotated[redis.Redis, Depends(get_redis)]


def _get_analytics(request: Request) -> AnalyticsClient:
    """Extract the AnalyticsClient from app state (set in lifespan)."""
    return request.app.state.analytics


def _get_report_client(request: Request) -> ReportClient:
    """Extract the ReportClient from app state (set in lifespan)."""
    return request.app.state.report_client


# gRPC client — telemetry, alerts, health queries via Analytics Service
Analytics = Annotated[AnalyticsClient, Depends(_get_analytics)]

# gRPC client — report status, listing, downloads via Report Service
Reports = Annotated[ReportClient, Depends(_get_report_client)]
