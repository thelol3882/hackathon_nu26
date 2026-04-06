"""FastAPI dependency aliases for DB sessions, gRPC clients, and Redis."""

from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.core.config import GatewaySettings, get_settings
from api_gateway.core.database import get_app_db_session
from api_gateway.core.redis_client import get_redis
from shared.grpc_client import AnalyticsClient, ReportClient

Settings = Annotated[GatewaySettings, Depends(get_settings)]

AppSession = Annotated[AsyncSession, Depends(get_app_db_session)]

# Backward-compatible alias
DbSession = AppSession

Redis = Annotated[redis.Redis, Depends(get_redis)]


def _get_analytics(request: Request) -> AnalyticsClient:
    return request.app.state.analytics


def _get_report_client(request: Request) -> ReportClient:
    return request.app.state.report_client


Analytics = Annotated[AnalyticsClient, Depends(_get_analytics)]

Reports = Annotated[ReportClient, Depends(_get_report_client)]
