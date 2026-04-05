"""
FastAPI dependencies for database sessions and Redis.

Two database sessions for two separate databases:
  AppSession — PostgreSQL, for auth / CRUD / config operations
  TsSession  — TimescaleDB, for historical telemetry queries

Routers pick the right session based on what they query:
  router_auth, router_locomotives (CRUD), router_reports, router_config → AppSession
  router_telemetry, router_alerts → TsSession
  router_locomotives (health) → TsSession for readings, Redis for config cache
"""

from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.core.config import GatewaySettings, get_settings
from api_gateway.core.database import get_app_db_session, get_ts_db_session
from api_gateway.core.redis_client import get_redis

Settings = Annotated[GatewaySettings, Depends(get_settings)]

# PostgreSQL — auth, locomotives, reports, health config
AppSession = Annotated[AsyncSession, Depends(get_app_db_session)]

# TimescaleDB — telemetry, alert history, health snapshots
TsSession = Annotated[AsyncSession, Depends(get_ts_db_session)]

# Backward-compatible alias (points to App DB)
DbSession = AppSession

Redis = Annotated[redis.Redis, Depends(get_redis)]
